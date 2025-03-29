import numpy as np
import random
import math
import svgwrite
from shapely.geometry import Point, LineString, Polygon
from shapely.ops import unary_union
from datetime import datetime
import os
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon
from matplotlib.collections import LineCollection, PatchCollection


class BloodgoodMultiStemGenerator:
    def __init__(self, width=800, height=1000):
        self.width = width
        self.height = height

        # Colors
        self.trunk_color = "#3A1F04"  # Darker brown for trunk
        self.highlight_color = "#D2691E"  # Lighter brown for highlights

        # Trunk parameters
        self.trunk_width_base = 12
        self.trunk_start_y = height * 0.9  # Start near bottom of canvas

        # The base point of our tree
        self.root_x = width // 2
        self.root_y = self.trunk_start_y

        # Dictionary to store all stems/branches as LineStrings
        self.stems = {}
        self.stem_id = 0

        # For generating natural-looking branching points
        self.min_branch_angle = math.pi / 12  # 15 degrees
        self.max_branch_angle = math.pi / 4  # 45 degrees

        # Control parameters for the multi-stem structure
        self.num_main_stems = random.randint(3, 5)  # 3-5 main stems
        self.branch_probability = 0.7  # Probability of a branch creating sub-branches
        self.max_branch_depth = 2  # Maximum depth of branching (beyond main stems)

    def generate_base_trunk(self):
        """Generate the base trunk from which multiple stems will emerge"""
        # Base trunk height - short base trunk for multi-stem trees
        base_height = self.height * 0.05  # Just 5% of total height

        # Create base trunk control points - slight curve possible
        curve_factor = self.width * 0.03
        mid_x = self.root_x + random.uniform(-curve_factor, curve_factor)

        points = [
            (self.root_x, self.root_y),
            (mid_x, self.root_y - base_height / 2),
            (self.root_x, self.root_y - base_height),
        ]

        # Create LineString for base trunk
        base_trunk = LineString(points)

        # Store trunk
        self.stems[self.stem_id] = {
            "line": base_trunk,
            "width": self.trunk_width_base,
            "level": 0,
            "parent": None,
            "is_main_stem": True,
        }

        base_trunk_id = self.stem_id
        self.stem_id += 1

        return base_trunk_id, points[-1]  # Return ID and end point

    def generate_stem(
        self, start_point, direction, length, width, level, is_main_stem=False
    ):
        """Generate a stem/branch with a natural curve and taper"""
        # Smooth, natural curve parameters
        num_control_points = 5 + level  # More points for more detail

        # Create a natural curve that generally follows the direction but with variation
        points = [start_point]

        # Current point starts at start_point
        current_x, current_y = start_point

        # Divide the total length into segments
        segment_length = length / (num_control_points - 1)

        # Create a natural curve with subtle variations
        for i in range(1, num_control_points):
            # Gradually reduce direction variation as we go higher
            # Main stems should be straighter, particularly near the base
            if is_main_stem:
                variation_factor = 0.1 * (i / num_control_points)
            else:
                variation_factor = 0.2

            # Adjust direction with some natural variation
            curr_direction = (
                direction
                + random.uniform(-math.pi / 12, math.pi / 12) * variation_factor
            )

            # Calculate new point
            new_x = current_x + segment_length * math.cos(curr_direction) * (
                0.9 + random.uniform(0, 0.2)
            )
            new_y = current_y + segment_length * math.sin(curr_direction) * (
                0.9 + random.uniform(0, 0.2)
            )

            # Apply gentle curve
            if i < num_control_points - 1:  # Not for the last point
                # Curve more pronounced in the middle
                curve_factor = (
                    segment_length * 0.1 * math.sin(math.pi * i / num_control_points)
                )
                perp_x = math.cos(direction + math.pi / 2) * curve_factor
                perp_y = math.sin(direction + math.pi / 2) * curve_factor

                # Apply the curve, sometimes to the left, sometimes to the right
                if random.random() < 0.5:
                    new_x += perp_x
                    new_y += perp_y
                else:
                    new_x -= perp_x
                    new_y -= perp_y

            points.append((new_x, new_y))
            current_x, current_y = new_x, new_y

        # Create LineString for stem
        stem = LineString(points)

        # Store stem with properties
        self.stems[self.stem_id] = {
            "line": stem,
            "width": width,
            "level": level,
            "parent": None,  # Will be set by the caller
            "is_main_stem": is_main_stem,
        }

        stem_id = self.stem_id
        self.stem_id += 1

        return stem_id, points[-1]  # Return ID and end point

    def generate_main_stems(self, base_trunk_id, base_end_point):
        """Generate the main stems that emerge from the base trunk"""
        main_stem_ids = []

        # Calculate initial directions for main stems
        # For a natural multi-stem look, we want the stems to spread out
        # but generally grow upward

        # Central stem - goes mostly straight up
        central_direction = -math.pi / 2  # Straight up
        central_direction += random.uniform(
            -math.pi / 12, math.pi / 12
        )  # Slight variation

        # Calculate stem heights - main central stem is tallest, others are shorter
        max_height = self.height * 0.7  # 70% of canvas height

        # Create a central, taller stem first
        central_length = max_height * (0.9 + random.uniform(0, 0.1))
        central_stem_id, central_end = self.generate_stem(
            base_end_point,
            central_direction,
            central_length,
            self.trunk_width_base * 0.8,  # Slightly narrower than base
            level=1,
            is_main_stem=True,
        )

        # Set parent relationship
        self.stems[central_stem_id]["parent"] = base_trunk_id
        main_stem_ids.append(central_stem_id)

        # Now create the side stems
        num_side_stems = self.num_main_stems - 1  # Already created the central stem

        # Create side stems with a natural spread
        for i in range(num_side_stems):
            # Alternate sides
            if i % 2 == 0:
                # Right side
                angle = random.uniform(math.pi / 12, math.pi / 4)
            else:
                # Left side
                angle = random.uniform(-math.pi / 4, -math.pi / 12)

            # Direction is mainly upward but with the calculated angle
            direction = -math.pi / 2 + angle

            # Side stems are shorter than central stem
            length_factor = 0.7 + random.uniform(0, 0.2)  # 70-90% of central stem
            stem_length = central_length * length_factor

            # Width decreases for stems that are more angled
            width_factor = 0.6 + (1 - abs(angle) / (math.pi / 4)) * 0.3
            stem_width = self.trunk_width_base * width_factor

            # Generate the stem
            stem_id, stem_end = self.generate_stem(
                base_end_point,
                direction,
                stem_length,
                stem_width,
                level=1,
                is_main_stem=True,
            )

            # Set parent relationship
            self.stems[stem_id]["parent"] = base_trunk_id
            main_stem_ids.append(stem_id)

        return main_stem_ids

    def add_secondary_branches(self, parent_stem_id, branch_depth=0):
        """Add secondary branches to a stem/branch"""
        if branch_depth >= self.max_branch_depth:
            return

        parent_stem = self.stems[parent_stem_id]
        parent_line = parent_stem["line"]
        parent_level = parent_stem["level"]

        # Get parent stem coordinates
        coords = list(parent_line.coords)

        # Determine number of branches to add
        if parent_stem["is_main_stem"]:
            # Main stems get more branches
            num_branches = random.randint(2, 4)
        else:
            # Secondary branches get fewer sub-branches
            num_branches = random.randint(1, 2)

        # Positions along the stem to add branches (avoid the very base)
        branch_positions = []
        for _ in range(num_branches):
            # Don't branch at the very start or end
            pos = random.uniform(0.3, 0.8)
            branch_positions.append(pos)

        # Sort positions from base to tip
        branch_positions.sort()

        # Create branches
        for pos in branch_positions:
            # Skip some positions randomly (for natural look)
            if random.random() > self.branch_probability:
                continue

            # Find the point along the parent stem
            index = int(pos * (len(coords) - 1))
            start_point = coords[index]

            # Calculate direction based on parent stem direction at this point
            if index < len(coords) - 1:
                # Calculate direction vector between current and next point
                dx = coords[index + 1][0] - coords[index][0]
                dy = coords[index + 1][1] - coords[index][1]
                parent_direction = math.atan2(dy, dx)
            else:
                # Use direction from previous point for the last point
                dx = coords[index][0] - coords[index - 1][0]
                dy = coords[index][1] - coords[index - 1][1]
                parent_direction = math.atan2(dy, dx)

            # Branch off to the left or right
            if random.random() < 0.5:
                direction = parent_direction - random.uniform(
                    self.min_branch_angle, self.max_branch_angle
                )
            else:
                direction = parent_direction + random.uniform(
                    self.min_branch_angle, self.max_branch_angle
                )

            # Length and width of branch (relative to parent)
            length = (
                parent_line.length * (0.4 + random.uniform(0, 0.3)) * (1 - pos * 0.5)
            )
            width = parent_stem["width"] * (0.5 + random.uniform(0, 0.2))

            # Generate the branch
            branch_id, branch_end = self.generate_stem(
                start_point,
                direction,
                length,
                width,
                level=parent_level + 1,
                is_main_stem=False,
            )

            # Set parent relationship
            self.stems[branch_id]["parent"] = parent_stem_id

            # Recursively add branches to this branch
            if random.random() < self.branch_probability * (
                1 - branch_depth / self.max_branch_depth
            ):
                self.add_secondary_branches(branch_id, branch_depth + 1)

    def generate_tree(self):
        """Generate the entire multi-stem tree structure"""
        # Generate base trunk
        base_trunk_id, base_end_point = self.generate_base_trunk()

        # Generate main stems
        main_stem_ids = self.generate_main_stems(base_trunk_id, base_end_point)

        # Add secondary branches to each main stem
        for stem_id in main_stem_ids:
            self.add_secondary_branches(stem_id)

    def draw_stems_with_thickness(self, dwg, group):
        """Draw stems with variable thickness"""
        for stem_id, stem_data in self.stems.items():
            line = stem_data["line"]
            width_base = stem_data["width"]

            # Convert LineString to a series of line segments for better thickness control
            coords = list(line.coords)

            # Draw every segment with appropriate thickness
            for i in range(len(coords) - 1):
                # Calculate taper - thinner toward the end
                taper_factor = 1 - (i / (len(coords) - 1)) * 0.5
                width = width_base * taper_factor

                # Draw line segment
                path = dwg.line(
                    start=coords[i],
                    end=coords[i + 1],
                    stroke=self.trunk_color,
                    stroke_width=width,
                    stroke_linecap="round",
                )
                group.add(path)

                # For main stems, add highlight line
                if stem_data["is_main_stem"] and width > 3:
                    # Calculate highlight position (offset toward light source)
                    highlight_offset = width * 0.15

                    # Simplistic lighting from top-right
                    highlight_x1 = coords[i][0] + highlight_offset
                    highlight_y1 = coords[i][1] - highlight_offset
                    highlight_x2 = coords[i + 1][0] + highlight_offset
                    highlight_y2 = coords[i + 1][1] - highlight_offset

                    # Add highlight
                    highlight = dwg.line(
                        start=(highlight_x1, highlight_y1),
                        end=(highlight_x2, highlight_y2),
                        stroke=self.highlight_color,
                        stroke_width=width * 0.2,
                        stroke_opacity=0.4,
                        stroke_linecap="round",
                    )
                    group.add(highlight)

    def export_svg(self, filename=None):
        """Export the tree trunk structure as an SVG file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"bloodgood_multistem_{timestamp}.svg"

        # Create SVG
        dwg = svgwrite.Drawing(
            filename, size=(f"{self.width}px", f"{self.height}px"), profile="tiny"
        )

        # Add white background
        dwg.add(dwg.rect(insert=(0, 0), size=(self.width, self.height), fill="white"))

        # Create trunk group
        trunk_group = dwg.add(dwg.g(id="trunk"))

        # Draw stems with thickness
        self.draw_stems_with_thickness(dwg, trunk_group)

        # Save SVG
        dwg.save()
        print(f"SVG saved to {filename}")
        return filename

    def create_preview(self, filename=None):
        """Create a PNG preview of the tree structure"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"bloodgood_multistem_{timestamp}_preview.png"

        # Create figure and axis
        fig, ax = plt.subplots(figsize=(self.width / 100, self.height / 100), dpi=100)
        ax.set_xlim(0, self.width)
        ax.set_ylim(0, self.height)

        # Draw stems
        for stem_id, stem_data in self.stems.items():
            line = stem_data["line"]
            width = stem_data["width"] / 2  # Adjust for matplotlib

            # Create segments from consecutive points
            coords = list(line.coords)
            segments = []
            for i in range(len(coords) - 1):
                segments.append([coords[i], coords[i + 1]])

            if segments:
                lc = LineCollection(segments, linewidths=width, colors=self.trunk_color)
                ax.add_collection(lc)

        # Final adjustments
        ax.set_facecolor("white")
        ax.axis("off")
        plt.tight_layout()

        # Save figure
        plt.savefig(filename, bbox_inches="tight", pad_inches=0)
        plt.close(fig)
        print(f"Preview saved to {filename}")
        return filename


def generate_multistem_maple(
    width=800, height=1000, output_file=None, generate_preview=True
):
    """
    Generate a Japanese Bloodgood Maple multi-stem trunk structure as SVG

    Parameters:
    width (int): Width of the SVG canvas
    height (int): Height of the SVG canvas
    output_file (str): Output filename (will generate a timestamped name if None)
    generate_preview (bool): Whether to generate a PNG preview

    Returns:
    tuple: Paths to the saved SVG file and PNG preview (if generated)
    """
    generator = BloodgoodMultiStemGenerator(width, height)
    generator.generate_tree()

    svg_file = generator.export_svg(output_file)

    if generate_preview:
        # Create preview with same base filename but PNG extension
        preview_file = os.path.splitext(svg_file)[0] + "_preview.png"
        generator.create_preview(preview_file)
        return svg_file, preview_file

    return svg_file, None


if __name__ == "__main__":
    # Generate a multi-stem maple with default parameters
    svg_file, preview_file = generate_multistem_maple(width=800, height=1000)
    print(f"Generated multi-stem trunk saved to: {svg_file}")
    if preview_file:
        print(f"Preview saved to: {preview_file}")
