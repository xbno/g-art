import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle, Polygon
from matplotlib.path import Path
from matplotlib.collections import PatchCollection, LineCollection
import random
import math
import svgwrite
from shapely.geometry import Point, Polygon as ShapelyPolygon, LineString, MultiPolygon
from shapely.ops import unary_union
import os
from datetime import datetime
import warnings

warnings.filterwarnings("ignore")  # Suppress shapely warnings


class Shape:
    def __init__(self, shape_type, x, y, size, color_index, z_index, rotation=0):
        self.type = shape_type
        self.x = x
        self.y = y
        self.size = size
        self.color_index = color_index
        self.z_index = z_index
        self.rotation = rotation
        self.points = self._generate_points()
        self.polygon = self._generate_shapely_polygon()

    def _generate_points(self):
        points = []
        if self.type == "circle":
            # Approximate circle with a regular polygon
            num_sides = 64
            radius = self.size / 2
            for i in range(num_sides):
                angle = 2 * math.pi * i / num_sides
                x = self.x + radius * math.cos(angle)
                y = self.y + radius * math.sin(angle)
                points.append((x, y))
        elif self.type == "square":
            half_size = self.size / 2
            points = [
                (self.x - half_size, self.y - half_size),
                (self.x + half_size, self.y - half_size),
                (self.x + half_size, self.y + half_size),
                (self.x - half_size, self.y + half_size),
            ]
        elif self.type == "triangle":
            for i in range(3):
                angle = 2 * math.pi * i / 3 + self.rotation
                x = self.x + self.size * math.cos(angle)
                y = self.y + self.size * math.sin(angle)
                points.append((x, y))
        return points

    def _generate_shapely_polygon(self):
        try:
            return ShapelyPolygon(self.points).buffer(
                0
            )  # Buffer 0 repairs any self-intersections
        except Exception as e:
            print(f"Error creating polygon: {e}")
            return ShapelyPolygon([(0, 0), (0, 1), (1, 1), (1, 0)])  # Fallback

    def get_matplotlib_patch(self, color):
        if self.type == "circle":
            return Circle((self.x, self.y), self.size / 2, fill=True, color=color)
        elif self.type == "square":
            half_size = self.size / 2
            return Rectangle(
                (self.x - half_size, self.y - half_size),
                self.size,
                self.size,
                fill=True,
                color=color,
            )
        elif self.type == "triangle":
            return Polygon(self.points, fill=True, color=color)

    def get_outline_segments(self):
        segments = []
        for i in range(len(self.points)):
            start = self.points[i]
            end = self.points[(i + 1) % len(self.points)]
            segments.append((start, end))
        return segments

    def contains_point(self, px, py):
        return self.polygon.contains(Point(px, py))


class HatchingGenerator:
    def __init__(self, width=1200, height=1800, num_shapes=40):
        self.width = width
        self.height = height
        self.shapes = self._generate_random_shapes(num_shapes)

        # Define color palette
        self.colors = ["#4361ee", "#4cc9f0", "#ef476f", "#ffd166", "#06d6a0"]

        # Define hatching patterns
        self.hatching_patterns = [
            {"angles": [0], "spacing": 12},  # Pattern 0: Horizontal
            {"angles": [15], "spacing": 12},  # Pattern 1: 15°
            {"angles": [30], "spacing": 12},  # Pattern 2: 30°
            {"angles": [45], "spacing": 12},  # Pattern 3: 45°
            {"angles": [60], "spacing": 12},  # Pattern 4: 60°
            {"angles": [75], "spacing": 12},  # Pattern 5: 75°
            {"angles": [90], "spacing": 12},  # Pattern 6: Vertical
            # Perpendicular pairs
            {"angles": [0, 90], "spacing": 12},  # Pattern 7: Grid
            {"angles": [15, 105], "spacing": 12},  # Pattern 8: 15°/105° grid
            {"angles": [30, 120], "spacing": 12},  # Pattern 9: 30°/120° grid
            {
                "angles": [45, 135],
                "spacing": 12,
            },  # Pattern 10: 45°/135° grid (diagonal crosshatch)
            # More random combinations
            {"angles": [0, 45], "spacing": 12},  # Pattern 11
            {"angles": [30, 75], "spacing": 12},  # Pattern 12
            {"angles": [15, 60], "spacing": 12},  # Pattern 13
            {"angles": [0, 30, 60, 90], "spacing": 20},  # Pattern 14
            {"angles": [15, 45, 75], "spacing": 18},  # Pattern 15
        ]

        # Assign colors to shapes
        self._assign_colors()

    def _generate_random_shapes(self, count):
        shapes = []
        padding = 50

        for i in range(count):
            x = random.uniform(padding, self.width - padding)
            y = random.uniform(padding, self.height - padding)
            shape_type = random.choice(["circle", "square", "triangle"])

            if shape_type == "circle":
                diameter = random.uniform(50, 240)
                if (
                    x - diameter / 2 >= padding
                    and x + diameter / 2 <= self.width - padding
                    and y - diameter / 2 >= padding
                    and y + diameter / 2 <= self.height - padding
                ):
                    shapes.append(Shape("circle", x, y, diameter, 0, i))

            elif shape_type == "square":
                size = random.uniform(50, 400)
                if (
                    x - size / 2 >= padding
                    and x + size / 2 <= self.width - padding
                    and y - size / 2 >= padding
                    and y + size / 2 <= self.height - padding
                ):
                    shapes.append(Shape("square", x, y, size, 0, i))

            else:  # triangle
                size = random.uniform(25, 400)
                rotation = random.randint(0, 3) * (math.pi / 2)
                # Simple check if triangle fits within bounds
                if (
                    x - size >= padding
                    and x + size <= self.width - padding
                    and y - size >= padding
                    and y + size <= self.height - padding
                ):
                    shapes.append(Shape("triangle", x, y, size, 0, i, rotation))

        return shapes

    def _assign_colors(self):
        for i, shape in enumerate(self.shapes):
            shape.color_index = i % len(self.colors)

    def calculate_effective_regions(self):
        """Calculate the effective regions for each shape, respecting z-index"""
        # Sort shapes by z-index (low to high)
        sorted_shapes = sorted(self.shapes, key=lambda s: s.z_index)

        # Create a list to hold processed regions for each shape
        shape_regions = []

        # Process shapes in z-index order (back to front)
        for shape in sorted_shapes:
            # Start with the original shape polygon
            region = shape.polygon

            # Iterate through all shapes with higher z-index
            for other_shape in sorted_shapes:
                if other_shape.z_index > shape.z_index:
                    try:
                        # Subtract any overlapping area from higher z-index shapes
                        if region.intersects(other_shape.polygon):
                            difference = region.difference(other_shape.polygon)
                            if not difference.is_empty:
                                region = difference
                            else:
                                # This shape is completely covered by higher z-index shapes
                                region = None
                                break
                    except Exception as e:
                        print(f"Error in difference operation: {e}")
                        # Continue with original region if difference fails
                        pass

            # If the shape isn't completely covered, add it to our regions
            if region is not None and not region.is_empty:
                shape_regions.append(
                    {"shape": shape, "region": region, "color_index": shape.color_index}
                )

        return shape_regions

    def generate_hatching_lines(self, shape_regions):
        """Generate hatching lines for each shape's effective region"""
        hatching_lines = {}

        # Process each shape's region
        for i, shape_data in enumerate(shape_regions):
            shape = shape_data["shape"]
            region = shape_data["region"]
            color_idx = shape_data["color_index"]

            # Initialize this color's lines list if it doesn't exist
            if color_idx not in hatching_lines:
                hatching_lines[color_idx] = []

            # Get the hatching pattern for this color
            pattern = self.hatching_patterns[color_idx % len(self.hatching_patterns)]

            try:
                # Calculate a bounding box for the region
                bounds = region.bounds  # (minx, miny, maxx, maxy)

                # Add padding to ensure coverage
                padding = 100
                minx, miny, maxx, maxy = bounds
                minx -= padding
                miny -= padding
                maxx += padding
                maxy += padding

                # Process each angle in the pattern
                for angle in pattern["angles"]:
                    # Calculate angle in radians
                    angle_rad = angle * (math.pi / 180)

                    # Calculate perpendicular direction
                    perp_angle = angle_rad + math.pi / 2
                    perp_x = math.cos(perp_angle)
                    perp_y = math.sin(perp_angle)

                    # Calculate diagonal length for full coverage
                    diagonal_length = math.sqrt((maxx - minx) ** 2 + (maxy - miny) ** 2)

                    # Calculate center point
                    center_x = (minx + maxx) / 2
                    center_y = (miny + maxy) / 2

                    # Calculate number of lines needed
                    spacing = pattern["spacing"]
                    num_lines = math.ceil(diagonal_length / spacing) * 2
                    start_offset = -diagonal_length / 2

                    # Direction vector
                    dir_x = math.cos(angle_rad)
                    dir_y = math.sin(angle_rad)

                    # Generate hatching lines
                    for i in range(num_lines):
                        offset = start_offset + i * spacing

                        # Calculate offset point
                        offset_x = perp_x * offset
                        offset_y = perp_y * offset

                        # Create a very long line
                        start_x = center_x + offset_x - dir_x * diagonal_length
                        start_y = center_y + offset_y - dir_y * diagonal_length
                        end_x = center_x + offset_x + dir_x * diagonal_length
                        end_y = center_y + offset_y + dir_y * diagonal_length

                        hatch_line = LineString([(start_x, start_y), (end_x, end_y)])

                        # Clip line to the region
                        try:
                            intersection = hatch_line.intersection(region)
                            if not intersection.is_empty:
                                if intersection.geom_type == "LineString":
                                    coords = list(intersection.coords)
                                    if len(coords) >= 2:  # Ensure we have valid line
                                        hatching_lines[color_idx].append(coords)
                                elif intersection.geom_type == "MultiLineString":
                                    for line in intersection.geoms:
                                        coords = list(line.coords)
                                        if (
                                            len(coords) >= 2
                                        ):  # Ensure we have valid line
                                            hatching_lines[color_idx].append(coords)
                                elif intersection.geom_type == "GeometryCollection":
                                    for geom in intersection.geoms:
                                        if geom.geom_type == "LineString":
                                            coords = list(geom.coords)
                                            if len(coords) >= 2:
                                                hatching_lines[color_idx].append(coords)
                        except Exception as e:
                            print(f"Error clipping line: {e}")
                            continue
            except Exception as e:
                print(f"Error processing region for shape with color {color_idx}: {e}")
                continue

        return hatching_lines

    def create_fixed_shape_scenario(self):
        """Create a fixed scenario with predictable shapes for testing"""
        self.shapes = []

        # Clear existing shapes and add new ones
        self.shapes = [
            Shape("square", 300, 300, 400, 0, 0),  # Large square in top left
            Shape("circle", 800, 300, 200, 1, 1),  # Circle top right
            Shape("circle", 350, 550, 100, 2, 2),  # Small circle middle
            Shape("triangle", 800, 900, 350, 3, 3),  # Triangle bottom right
            Shape("square", 800, 1200, 300, 4, 4),  # Square bottom right
        ]

        # Ensure all shapes have the correct color_index
        for i, shape in enumerate(self.shapes):
            shape.color_index = i % len(self.colors)

        return self.shapes

    def find_composite_outline(self):
        """Find the outline segments of the composite shape"""
        try:
            # Get all shape polygons
            all_polygons = []
            for shape in self.shapes:
                # Make sure each polygon is valid
                if shape.polygon is not None and not shape.polygon.is_empty:
                    all_polygons.append(shape.polygon)

            if not all_polygons:
                return []

            # Calculate the union of all shapes
            merged = unary_union(all_polygons)

            # Extract the exterior coordinates
            segments = []

            if merged.geom_type == "Polygon":
                exterior_coords = list(merged.exterior.coords)
                segments = [
                    (
                        (exterior_coords[i][0], exterior_coords[i][1]),
                        (exterior_coords[i + 1][0], exterior_coords[i + 1][1]),
                    )
                    for i in range(len(exterior_coords) - 1)
                ]

            elif merged.geom_type == "MultiPolygon":
                for poly in merged.geoms:
                    exterior_coords = list(poly.exterior.coords)
                    segments.extend(
                        [
                            (
                                (exterior_coords[i][0], exterior_coords[i][1]),
                                (exterior_coords[i + 1][0], exterior_coords[i + 1][1]),
                            )
                            for i in range(len(exterior_coords) - 1)
                        ]
                    )

            return segments

        except Exception as e:
            print(f"Error finding composite outline: {e}")

            # Fallback: return individual shape segments
            segments = []
            for shape in self.shapes:
                segments.extend(shape.get_outline_segments())
            return segments

    def visualize(self, show_hatching=False):
        """Visualize the shapes and optionally the hatching patterns"""
        fig, ax = plt.subplots(figsize=(12, 18))
        ax.set_xlim(0, self.width)
        ax.set_ylim(0, self.height)

        # Draw filled shapes
        for shape in self.shapes:
            color = self.colors[shape.color_index % len(self.colors)]
            patch = shape.get_matplotlib_patch(color)
            ax.add_patch(patch)

        # Calculate and draw the composite outline
        outline_segments = self.find_composite_outline()
        outline_collection = LineCollection(
            outline_segments, colors="black", linewidths=2
        )
        ax.add_collection(outline_collection)

        if show_hatching:
            # Calculate effective regions and hatching lines
            shape_regions = self.calculate_effective_regions()
            hatching_lines = self.generate_hatching_lines(shape_regions)

            # Draw hatching lines
            for color_idx, lines in hatching_lines.items():
                line_collection = LineCollection(lines, colors="black", linewidths=0.5)
                ax.add_collection(line_collection)

        # Add debug text for each shape
        for shape in self.shapes:
            ax.text(
                shape.x,
                shape.y,
                f"C{shape.color_index}",
                ha="center",
                va="center",
                fontsize=12,
                color="white",
                fontweight="bold",
            )

        ax.set_aspect("equal")
        ax.axis("off")
        plt.tight_layout()
        plt.show()

    def visualize_color_regions(self):
        """Visualize the effective regions for each shape"""
        fig, ax = plt.subplots(figsize=(12, 18))
        ax.set_xlim(0, self.width)
        ax.set_ylim(0, self.height)

        # Draw filled shapes first
        for shape in self.shapes:
            color = self.colors[shape.color_index % len(self.colors)]
            patch = shape.get_matplotlib_patch(color)
            ax.add_patch(patch)

        # Calculate effective regions
        shape_regions = self.calculate_effective_regions()

        # Draw outlines around effective regions for each shape
        outline_colors = ["red", "green", "blue", "orange", "purple"]

        for i, shape_data in enumerate(shape_regions):
            shape = shape_data["shape"]
            region = shape_data["region"]
            color_idx = shape_data["color_index"]

            outline_color = outline_colors[color_idx % len(outline_colors)]

            try:
                if isinstance(region, ShapelyPolygon):
                    # Extract coordinates from the polygon
                    x, y = region.exterior.xy
                    ax.plot(x, y, color=outline_color, linestyle="--", linewidth=2)

                    # Add a label in the center of the region
                    centroid = region.centroid
                    ax.text(
                        centroid.x,
                        centroid.y,
                        f"C{color_idx}",
                        ha="center",
                        va="center",
                        fontsize=14,
                        color=outline_color,
                        fontweight="bold",
                    )
                elif isinstance(region, MultiPolygon):
                    for poly in region.geoms:
                        x, y = poly.exterior.xy
                        ax.plot(x, y, color=outline_color, linestyle="--", linewidth=2)
            except Exception as e:
                print(f"Error visualizing region: {e}")
                continue

        # Add the main black outline
        outline_segments = self.find_composite_outline()
        outline_collection = LineCollection(
            outline_segments, colors="black", linewidths=2
        )
        ax.add_collection(outline_collection)

        ax.set_aspect("equal")
        ax.axis("off")
        plt.tight_layout()
        plt.show()

    def export_svg(self, filename=None):
        """Export the design as an SVG file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"plotter_hatching_{timestamp}.svg"

        # Calculate effective regions and hatching lines
        shape_regions = self.calculate_effective_regions()
        hatching_lines = self.generate_hatching_lines(shape_regions)

        # Find composite outline
        outline_segments = self.find_composite_outline()

        # Create SVG
        dwg = svgwrite.Drawing(
            filename, size=(f"{self.width}px", f"{self.height}px"), profile="tiny"
        )

        # Add white background
        dwg.add(dwg.rect(insert=(0, 0), size=(self.width, self.height), fill="white"))

        # Add hatching groups for each color
        for color_idx, lines in hatching_lines.items():
            g = dwg.add(dwg.g(id=f"color-{color_idx}"))
            for line in lines:
                if (
                    len(line) >= 2
                ):  # Make sure the line has at least start and end points
                    g.add(
                        dwg.line(
                            start=line[0], end=line[1], stroke="black", stroke_width=1
                        )
                    )

        # Add outline
        g_outline = dwg.add(dwg.g(id="outlines"))
        for segment in outline_segments:
            g_outline.add(
                dwg.line(
                    start=segment[0], end=segment[1], stroke="black", stroke_width=10
                )
            )

        # Save SVG
        dwg.save()
        print(f"SVG saved to {filename}")

        return filename


# Usage example
if __name__ == "__main__":
    # Create the generator
    generator = HatchingGenerator(width=1200, height=1800, num_shapes=40)

    # Optionally use a fixed scenario for debugging
    # generator.create_fixed_shape_scenario()

    # Visualize shapes with color labels
    generator.visualize(show_hatching=False)

    # Visualize effective color regions
    generator.visualize_color_regions()

    # Visualize with hatching lines
    generator.visualize(show_hatching=True)

    # Export SVG to downloads folder
    downloads_path = os.path.expanduser("~/Downloads")
    svg_file = generator.export_svg(os.path.join(downloads_path, "hatching.svg"))
    print(f"SVG exported to: {svg_file}")
