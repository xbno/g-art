# inspiration:
# https://utpaqp.edu.pe/post/premium-vector-abstract-waves-graphic-line-sonic-or-sound-wave/wave-line-texture
# https://utpaqp.edu.pe/post/wave-texture-background/wave-line-texture
# http://etudes.tiao.io/auto_examples/misc/plot_perlin_noise.html
# https://ragingnexus.com/creative-code-lab/experiments/perlin-noise-flow-field/

import random
import os
import math
import xml.etree.ElementTree as ET
import numpy as np


def generate_random_wavy_pattern(
    width=800,
    height=600,
    num_waves=15,
    min_wave_height=10,
    max_wave_height=50,
    min_wavelength=50,
    max_wavelength=150,
    min_stroke_width=1,
    max_stroke_width=4,
    line_spacing=20,
    randomness=0.3,
    variation_frequency=2,
    seed=None,
):
    """
    Generate a random wavy pattern SVG similar to the optical illusion image.

    Parameters:
    -----------
    width: int
        Width of the SVG canvas
    height: int
        Height of the SVG canvas
    num_waves: int
        Number of waves to generate vertically
    min_wave_height, max_wave_height: float
        Range of wave amplitude/height
    min_wavelength, max_wavelength: float
        Range of wavelength values
    min_stroke_width, max_stroke_width: float
        Range of stroke widths
    line_spacing: float
        Base spacing between lines
    randomness: float
        Amount of random variation (0-1)
    variation_frequency: float
        How frequently the wave parameters change
    seed: int
        Random seed for reproducibility

    Returns:
    --------
    str: SVG content as string
    """
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    # Create the SVG root element
    svg = ET.Element(
        "svg",
        {
            "xmlns": "http://www.w3.org/2000/svg",
            "width": str(width),
            "height": str(height),
            "viewBox": f"0 0 {width} {height}",
        },
    )

    # Create a group for all paths
    g = ET.SubElement(svg, "g", {"fill": "none", "stroke": "black"})

    # Calculate how many points we need horizontally
    points_per_wave = 20  # Number of control points per wave
    num_points = int((width / min_wavelength) * points_per_wave)

    # Generate random variation parameters
    x_points = np.linspace(0, width, num_points)

    # Generate all wave paths
    for line_idx in range(num_waves):
        # Base y-position
        base_y = line_idx * line_spacing

        # Randomize wave parameters for this line
        wave_height = random.uniform(min_wave_height, max_wave_height)
        wave_height *= 1 + random.uniform(-randomness, randomness)

        wavelength = random.uniform(min_wavelength, max_wavelength)
        wavelength *= 1 + random.uniform(-randomness, randomness)

        phase_shift = random.uniform(0, 2 * math.pi)

        # Generate random scaling factors along the path
        # This creates areas of higher and lower amplitude
        amplitude_variation = np.sin(
            np.linspace(0, variation_frequency * 2 * math.pi, num_points)
        )
        amplitude_variation = 1 + (amplitude_variation * randomness)

        # Generate the wavy path points
        path_points = []
        for i, x in enumerate(x_points):
            # Base sine wave
            sine_val = math.sin((x / wavelength) * 2 * math.pi + phase_shift)

            # Apply variation
            amplitude = wave_height * amplitude_variation[i]

            # Add random jitter
            jitter = random.uniform(-randomness * 5, randomness * 5)

            y = base_y + (sine_val * amplitude) + jitter
            path_points.append((x, y))

        # Create SVG path
        path_d = f"M {path_points[0][0]},{path_points[0][1]}"

        # Use cubic bezier curves for smoother paths
        i = 0
        while i < len(path_points) - 1:
            # Calculate control points
            if i < len(path_points) - 3:
                # Use cubic bezier with calculated control points
                x1, y1 = path_points[i]
                x4, y4 = path_points[i + 3]

                # Control points at 1/3 and 2/3 distance
                x2 = x1 + (x4 - x1) / 3
                y2 = path_points[i + 1][1]

                x3 = x1 + 2 * (x4 - x1) / 3
                y3 = path_points[i + 2][1]

                path_d += f" C {x2},{y2} {x3},{y3} {x4},{y4}"
                i += 3
            else:
                # For remaining points, use line
                x, y = path_points[i + 1]
                path_d += f" L {x},{y}"
                i += 1

        # Randomize stroke width
        stroke_width = random.uniform(min_stroke_width, max_stroke_width)

        # Create the path element
        ET.SubElement(g, "path", {"d": path_d, "stroke-width": str(stroke_width)})

    # Convert to string
    return ET.tostring(svg, encoding="unicode")


import numpy as np
import math
import xml.etree.ElementTree as ET
from opensimplex import OpenSimplex


def generate_flowing_lines_pattern(
    width=800,
    height=600,
    num_lines=70,
    line_spacing=8,
    noise_scale=0.003,
    distortion_strength=20,
    stroke_width=0.7,
    seed=None,
):
    """
    Generate a pattern of flowing parallel lines distorted by a noise field.

    Parameters:
    -----------
    width: int
        Width of the SVG canvas
    height: int
        Height of the SVG canvas
    num_lines: int
        Number of lines to generate
    line_spacing: float
        Base spacing between lines
    noise_scale: float
        Scale of the noise (smaller = smoother, larger = more chaotic)
    distortion_strength: float
        How much the lines are distorted by the noise field
    stroke_width: float
        Width of the lines
    seed: int
        Random seed for reproducibility

    Returns:
    --------
    str: SVG content as string
    """
    if seed is not None:
        np.random.seed(seed)
        noise_gen = OpenSimplex(seed=seed)
    else:
        noise_gen = OpenSimplex()

    # Create the SVG root element
    svg = ET.Element(
        "svg",
        {
            "xmlns": "http://www.w3.org/2000/svg",
            "width": str(width),
            "height": str(height),
            "viewBox": f"0 0 {width} {height}",
        },
    )

    # Create a group for all paths
    g = ET.SubElement(
        svg, "g", {"fill": "none", "stroke": "black", "stroke-width": str(stroke_width)}
    )

    # Calculate the number of points along each line
    points_per_line = int(width / 5)  # A point every 5 pixels for smooth curves

    # Generate grid of points for all lines
    x_coords = np.linspace(0, width, points_per_line)

    # Generate all lines
    for line_idx in range(num_lines):
        # Base y-position for this line
        base_y = line_idx * line_spacing

        # Generate the path points with noise distortion
        path_points = []
        for x in x_coords:
            # Sample noise at this position
            # We use different noise functions for different dimensions to create more complex patterns
            noise_value_y = noise_gen.noise2(x=x * noise_scale, y=base_y * noise_scale)

            # Apply distortion
            y = base_y + (noise_value_y * distortion_strength * 3)

            # Add additional distortion based on position
            secondary_noise = noise_gen.noise2(
                x=x * noise_scale * 2.5, y=base_y * noise_scale * 2.5 + 1000
            )
            y += secondary_noise * distortion_strength

            path_points.append((x, y))

        # Create SVG path
        path_d = f"M {path_points[0][0]},{path_points[0][1]}"

        # Use cubic bezier curves for smooth paths
        i = 0
        while i < len(path_points) - 3:
            # Get four points for the cubic bezier
            p0 = path_points[i]
            p1 = path_points[i + 1]
            p2 = path_points[i + 2]
            p3 = path_points[i + 3]

            # Calculate control points
            # First control point
            ctrl1_x = p0[0] + (p1[0] - p0[0]) * 0.5
            ctrl1_y = p1[1]

            # Second control point
            ctrl2_x = p3[0] - (p3[0] - p2[0]) * 0.5
            ctrl2_y = p2[1]

            # Add the cubic bezier curve
            path_d += f" C {ctrl1_x},{ctrl1_y} {ctrl2_x},{ctrl2_y} {p3[0]},{p3[1]}"

            i += 3

        # Add remaining points with lines if any
        while i < len(path_points) - 1:
            i += 1
            path_d += f" L {path_points[i][0]},{path_points[i][1]}"

        # Create the path element
        ET.SubElement(g, "path", {"d": path_d})

    # Convert to string
    return ET.tostring(svg, encoding="unicode")


def save_svg(svg_content, filename):
    """Save the SVG content to a file"""
    with open(filename, "w") as f:
        f.write('<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n')
        f.write(svg_content)


def save_svg(svg_content, filename):
    """Save the SVG content to a file"""
    with open(filename, "w") as f:
        f.write(svg_content)


# # Example usage
# if __name__ == "__main__":
#     # Generate with default parameters
#     svg_content = generate_random_wavy_pattern(
#         width=800,
#         height=600,
#         num_waves=20,
#         randomness=0.3,
#         line_spacing=25,
#         seed=42,  # Set seed for reproducibility
#     )
#     save_svg(svg_content, "random_wavy_pattern.svg")

#     # Generate more chaotic version
#     svg_content = generate_random_wavy_pattern(
#         width=800,
#         height=600,
#         num_waves=25,
#         randomness=0.5,
#         variation_frequency=4,
#         line_spacing=20,
#         seed=123,
#     )
#     save_svg(svg_content, "chaotic_wavy_pattern.svg")


import numpy as np
import math
import xml.etree.ElementTree as ET
import noise  # pip install noise


def generate_topographic_wave_pattern(
    width=800,
    height=800,
    num_lines=60,
    noise_scale=0.005,
    distortion_strength=50,
    line_width_variation=True,
    min_stroke_width=0.5,
    max_stroke_width=2.0,
    line_spacing=12,
    octaves=2,
    persistence=0.5,
    lacunarity=2.0,
    seed=None,
):
    """
    Generate a topographic-like wave pattern with variable thickness lines.

    Parameters:
    -----------
    width, height: int
        Dimensions of the SVG canvas
    num_lines: int
        Number of lines to generate
    noise_scale: float
        Scale of the noise (smaller = smoother)
    distortion_strength: float
        How much the lines are distorted by the noise
    line_width_variation: bool
        Whether to vary line thickness (alternating)
    min_stroke_width, max_stroke_width: float
        Range for line thickness
    line_spacing: float
        Spacing between lines
    octaves, persistence, lacunarity: float
        Parameters controlling the Perlin noise complexity
    seed: int
        Random seed for reproducibility

    Returns:
    --------
    str: SVG content as string
    """
    if seed is not None:
        np.random.seed(seed)

    # Create the SVG root element
    svg = ET.Element(
        "svg",
        {
            "xmlns": "http://www.w3.org/2000/svg",
            "width": str(width),
            "height": str(height),
            "viewBox": f"0 0 {width} {height}",
        },
    )

    # Calculate the number of points along each line
    points_per_line = int(width / 4)  # A point every 4 pixels for smooth curves

    # Generate x coordinates
    x_coords = np.linspace(0, width, points_per_line)

    # Create central noise field with interesting features
    # Generate a grid of central points for distortion focus
    center_points = []
    for i in range(3):
        for j in range(3):
            x = width * (0.2 + 0.3 * i)
            y = height * (0.2 + 0.3 * j)
            strength = np.random.uniform(0.5, 1.5)
            center_points.append((x, y, strength))

    # Generate all lines
    for line_idx in range(num_lines):
        # Base y-position
        base_y = line_idx * line_spacing

        # Determine line thickness - alternate between thin and thick
        if line_width_variation:
            # Gradually vary thickness
            position_factor = 0.5 + 0.5 * math.sin(line_idx / 10.0)
            # Add some randomness to thickness
            random_factor = 0.7 + 0.3 * np.random.random()
            stroke_width = (
                min_stroke_width
                + (max_stroke_width - min_stroke_width)
                * position_factor
                * random_factor
            )
        else:
            stroke_width = min_stroke_width

        # Generate the path points with noise distortion
        path_points = []
        for x in x_coords:
            # Base 2D Perlin noise
            noise_value = noise.pnoise2(
                x * noise_scale,
                base_y * noise_scale,
                octaves=octaves,
                persistence=persistence,
                lacunarity=lacunarity,
                repeatx=width,
                repeaty=height,
                base=seed if seed else 0,
            )

            # Add distortion from central points
            central_influence = 0
            for cx, cy, strength in center_points:
                # Calculate distance from this point to the center
                dx = x - cx
                dy = base_y - cy
                distance = math.sqrt(dx * dx + dy * dy)

                # Inverse square falloff
                if distance > 0:
                    falloff = 1.0 / (1.0 + distance / 200.0)
                    # Circular wave pattern from this center
                    wave = math.sin(distance * 0.03)
                    central_influence += wave * falloff * strength

            # Combine noise and central influence
            y = (
                base_y
                + (noise_value * distortion_strength)
                + (central_influence * distortion_strength * 0.8)
            )

            path_points.append((x, y))

        # Create SVG path
        path_d = f"M {path_points[0][0]},{path_points[0][1]}"

        # Use cubic bezier curves for smooth paths
        i = 0
        while i < len(path_points) - 3:
            # Get four points for the cubic bezier
            p0 = path_points[i]
            p1 = path_points[i + 1]
            p2 = path_points[i + 2]
            p3 = path_points[i + 3]

            # Calculate control points
            # First control point - use the point itself plus a portion toward the next point
            ctrl1_x = p0[0] + (p1[0] - p0[0]) * 0.5
            ctrl1_y = p1[1]

            # Second control point - use a portion from the end point back toward the previous point
            ctrl2_x = p3[0] - (p3[0] - p2[0]) * 0.5
            ctrl2_y = p2[1]

            # Add the cubic bezier curve
            path_d += f" C {ctrl1_x},{ctrl1_y} {ctrl2_x},{ctrl2_y} {p3[0]},{p3[1]}"

            i += 3

        # Add remaining points with lines if any
        while i < len(path_points) - 1:
            i += 1
            path_d += f" L {path_points[i][0]},{path_points[i][1]}"

        # Create the path element
        ET.SubElement(
            svg,
            "path",
            {
                "d": path_d,
                "stroke": "black",
                "stroke-width": str(stroke_width),
                "fill": "none",
            },
        )

    # Convert to string
    return ET.tostring(svg, encoding="unicode")


if __name__ == "__main__":
    import argparse

    # Set up argument parser
    parser = argparse.ArgumentParser(description="Generate a wavy pattern SVG")
    parser.add_argument(
        "--pattern", type=str, default="flowing", help="Pattern type: wavey or flowing"
    )
    parser.add_argument("--width", type=int, default=800, help="Width of SVG canvas")
    parser.add_argument("--height", type=int, default=600, help="Height of SVG canvas")
    parser.add_argument(
        "--num-waves", type=int, default=20, help="Number of waves to generate"
    )
    parser.add_argument(
        "--randomness", type=float, default=0.3, help="Amount of random variation (0-1)"
    )
    parser.add_argument(
        "--line-spacing", type=int, default=6, help="Spacing between lines"
    )
    parser.add_argument(
        "--num-lines", type=int, default=100, help="Number of lines for flowing pattern"
    )
    parser.add_argument(
        "--noise-scale",
        type=float,
        default=0.0025,
        help="Noise scale for flowing pattern",
    )
    parser.add_argument(
        "--distortion-strength",
        type=float,
        default=65,
        help="Distortion strength for flowing pattern",
    )
    parser.add_argument(
        "--stroke-width",
        type=float,
        default=0.6,
        help="Stroke width for flowing pattern",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    if args.pattern == "wavey":
        # Generate pattern using args
        svg_content = generate_random_wavy_pattern(
            width=args.width,
            height=args.height,
            num_waves=args.num_waves,
            randomness=args.randomness,
            line_spacing=args.line_spacing,
            seed=args.seed,
        )
    elif args.pattern == "flowing":
        # Generate flowing lines pattern
        svg_content = generate_flowing_lines_pattern(
            width=args.width,
            height=args.height,
            num_lines=args.num_lines,
            line_spacing=args.line_spacing,
            noise_scale=args.noise_scale,
            distortion_strength=args.distortion_strength,
            stroke_width=args.stroke_width,
            seed=args.seed,
        )
    elif args.pattern == "topographic":
        # Generate topographic wave pattern
        svg_content = generate_topographic_wave_pattern(
            width=800,
            height=800,
            num_lines=65,
            line_spacing=12,
            noise_scale=0.005,
            distortion_strength=40,
            min_stroke_width=0.5,
            max_stroke_width=2.0,
            line_width_variation=True,
            seed=42,
        )

    # Save to file
    downloads_path = os.path.expanduser("~/Downloads")
    save_svg(svg_content, os.path.join(downloads_path, "wavy_pattern.svg"))
