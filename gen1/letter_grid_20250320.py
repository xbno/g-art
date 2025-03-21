import random
import svgwrite
import matplotlib.pyplot as plt
from cairosvg import svg2png
import io
import math
import matplotlib

matplotlib.use("Agg")  # Add this near the top of your script, before importing pyplot
import matplotlib.pyplot as plt


def create_staggered_letter_grid(
    width=800,
    height=800,
    cell_size=40,  # Base size for grid cells
    letter_size=None,  # Font size
    grid_angle=45,  # Angle of rotation for the grid in degrees
    stagger_offset=0.5,  # Offset for staggered rows (0.5 = half cell)
    horizontal_spacing=1.0,
    vertical_spacing=1.0,
    highlight_pattern="aurea",
    output_filename="staggered_letter_grid.svg",
    show_preview=True,
):
    # Set default letter size if not specified
    if letter_size is None:
        letter_size = cell_size // 2

    # Calculate actual spacings
    h_spacing = cell_size * horizontal_spacing
    v_spacing = cell_size * vertical_spacing

    # Create SVG drawing
    dwg = svgwrite.Drawing(output_filename, size=(f"{width}px", f"{height}px"))

    # Define the sequence
    # sequence = ["a", "u", "r", "e"]
    sequence = ["e", "r", "u", "a"]

    # Calculate grid dimensions
    # Add extra rows/cols to compensate for rotation and ensure the canvas is filled
    cols = int(width / h_spacing * 1.5) + 1
    rows = int(height / v_spacing * 1.5) + 1

    # Create a matrix to track where letters have been placed
    grid = [[" " for _ in range(cols)] for _ in range(rows)]

    # Create groups for different letter styles
    outlined_letters = dwg.add(
        dwg.g(
            font_family="'Roboto Mono', monospace",
            font_size=f"{letter_size}px",
            fill="none",
            stroke="black",
            stroke_width="0.5",
        )
    )

    crosshatched_letters = dwg.add(
        dwg.g(font_family="'Roboto Mono', monospace", font_size=f"{letter_size}px")
    )

    # Create a pattern for cross-hatching
    pattern_size = 10
    pattern = dwg.defs.add(
        dwg.pattern(
            id="crosshatch",
            patternUnits="userSpaceOnUse",
            size=(pattern_size, pattern_size),
        )
    )

    # Add lines for the crosshatch pattern
    pattern.add(
        dwg.line(
            start=(0, 0),
            end=(pattern_size, pattern_size),
            stroke="black",
            stroke_width="0.5",
        )
    )
    pattern.add(
        dwg.line(
            start=(pattern_size, 0),
            end=(0, pattern_size),
            stroke="black",
            stroke_width="0.5",
        )
    )

    # Calculate the center of the canvas for rotation
    center_x = width / 2
    center_y = height / 2

    # Convert grid angle to radians
    angle_rad = math.radians(grid_angle)

    # Track positions of potential highlight patterns
    pattern_positions = []
    letter_positions = []

    # Function to rotate a point around the center
    def rotate_point(x, y, cx, cy, angle):
        # Translate point to origin
        x_shifted = x - cx
        y_shifted = y - cy

        # Rotate point
        x_rotated = x_shifted * math.cos(angle) - y_shifted * math.sin(angle)
        y_rotated = x_shifted * math.sin(angle) + y_shifted * math.cos(angle)

        # Translate back
        x_final = x_rotated + cx
        y_final = y_rotated + cy

        return x_final, y_final

    # Generate staggered grid points and place letters
    for row in range(-rows // 2, rows // 2):
        for col in range(-cols // 2, cols // 2):
            # Apply staggering to odd rows
            stagger = (stagger_offset * h_spacing) if row % 2 == 1 else 0

            # Calculate base position
            base_x = center_x + col * h_spacing + stagger
            base_y = center_y + row * v_spacing

            # Rotate the point
            x, y = rotate_point(base_x, base_y, center_x, center_y, angle_rad)

            # Skip if outside canvas with some margin
            margin = 100  # Pixels margin to ensure we cover the edges
            if x < -margin or x > width + margin or y < -margin or y > height + margin:
                continue

            # Determine which letter to place based on position
            # We'll use a rule that cycles through the sequence
            letter_idx = (abs(row) + abs(col)) % len(sequence)
            letter = sequence[letter_idx]

            # Add to letter positions
            letter_positions.append((x, y, letter, letter_idx))

    # Sort letter positions to create interesting patterns
    # This can create continuous sequences for highlighting
    letter_positions.sort(key=lambda pos: (pos[1] // (v_spacing / 2), pos[0]))

    # Find pattern matches in the sorted positions
    for i in range(len(letter_positions) - len(highlight_pattern) + 1):
        possible_pattern = ""
        for j in range(len(highlight_pattern)):
            possible_pattern += letter_positions[i + j][2]

        if possible_pattern == highlight_pattern:
            pattern_positions.append(i)

    # Place letters
    for i, (x, y, letter, letter_idx) in enumerate(letter_positions):
        # Add to appropriate group - all letters start as outlines
        outlined_letters.add(dwg.text(letter, insert=(x, y), text_anchor="middle"))

    # Add crosshatched letters for the highlighted pattern
    for start_idx in pattern_positions:
        for i in range(len(highlight_pattern)):
            x, y, letter, _ = letter_positions[start_idx + i]

            # Add a crosshatched version of this letter
            text = dwg.text(letter, insert=(x, y), text_anchor="middle")
            text.fill(pattern.get_paint_server())
            crosshatched_letters.add(text)

    # Save the SVG file
    dwg.save()
    print(f"Created staggered letter grid in '{output_filename}'")

    # Display preview in the notebook if requested
    if show_preview:
        try:
            # Convert SVG to PNG bytes
            svg_string = dwg.tostring()
            png_bytes = io.BytesIO()
            svg2png(bytestring=svg_string, write_to=png_bytes)
            png_bytes.seek(0)

            # Display the image
            plt.figure(figsize=(12, 12))
            plt.imshow(plt.imread(png_bytes, format="png"))
            plt.axis("off")
            plt.title(
                f"Staggered Letter Grid (angle: {grid_angle}°) with crosshatched '{highlight_pattern}' pattern"
            )
            plt.savefig(output_filename.replace(".svg", "_preview.png"))
            plt.close()
        except Exception as e:
            print(f"Preview failed: {e}")
            print("The SVG file was still created successfully.")

    return output_filename


# Example usage
if __name__ == "__main__":
    create_staggered_letter_grid(
        cell_size=40,
        letter_size=18,
        grid_angle=45,
        stagger_offset=0.5,
        horizontal_spacing=1.0,
        vertical_spacing=1.0,
        highlight_pattern="aurea",
        output_filename="staggered_crosshatched_pattern.svg",
        show_preview=True,
    )
