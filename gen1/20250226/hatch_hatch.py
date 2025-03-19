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
    def __init__(self, width=500, height=500, num_shapes=40, show_colors=True):
        self.width = width
        self.height = height
        self.shapes = self._generate_random_shapes(num_shapes)
        self.show_colors = show_colors
        # Define color palette
        self.colors = ["#4361ee", "#4cc9f0", "#ef476f", "#ffd166", "#06d6a0"]

        # Define hatching patterns
        self.hatching_patterns = [
            # cooler ones
            # {
            #     "angles": [45],
            #     "spacing": 4,
            #     "style": "regular",  # Default style - evenly spaced lines
            # },
            # {
            #     "angles": [0],
            #     "spacing": 2,
            #     "style": "exponential",
            #     "exp_factor": 1.1,  # Each gap is 1.5x larger than the previous
            # },
            # {
            #     "angles": [30],
            #     "spacing": 6,
            #     "style": "wavy",
            #     "wave_amplitude": 5,
            #     "wave_frequency": 0.1,
            #     "num_points": 20,  # More points = smoother waves
            # },
            # {
            #     "angles": [60],
            #     "spacing": 8,
            #     "style": "noisy",
            #     "noise_scale": 0.1,
            #     "noise_amplitude": 10,
            #     "num_points": 15,  # More points = more detailed noise
            # },
            {"angles": [-45], "spacing": 3},  # Pattern 3: 45°
            {"angles": [45], "spacing": 3},  # Pattern 3: 45°
            {"angles": [-15], "spacing": 3},  # Pattern 1: 15°
            {"angles": [15], "spacing": 3},  # Pattern 1: 15°
            {"angles": [-30], "spacing": 3},  # Pattern 2: 30°
            {"angles": [30], "spacing": 3},  # Pattern 2: 30°
            {"angles": [-60], "spacing": 3},  # Pattern 4: 60°
            {"angles": [60], "spacing": 3},  # Pattern 4: 60°
            {"angles": [-75], "spacing": 3},  # Pattern 5: 75°
            {"angles": [75], "spacing": 3},  # Pattern 5: 75°
            {"angles": [0], "spacing": 3},  # Pattern 0: Horizontal
            {"angles": [90], "spacing": 3},  # Pattern 6: Vertical
            # Perpendicular pairs
            {"angles": [0, 90], "spacing": 3},  # Pattern 7: Grid
            {"angles": [15, 105], "spacing": 3},  # Pattern 8: 15°/105° grid
            {"angles": [30, 120], "spacing": 3},  # Pattern 9: 30°/120° grid
            {
                "angles": [45, 135],
                "spacing": 6,
            },  # Pattern 10: 45°/135° grid (diagonal crosshatch)
            # More random combinations
            {"angles": [0, 45], "spacing": 6},  # Pattern 11
            {"angles": [30, 75], "spacing": 6},  # Pattern 12
            {"angles": [15, 60], "spacing": 6},  # Pattern 13
            {"angles": [0, 30, 60, 90], "spacing": 20},  # Pattern 14
            {"angles": [15, 45, 75], "spacing": 18},  # Pattern 15
        ]

        # Assign colors to shapes
        self._assign_colors()

    def _generate_random_shapes(self, count, padding=50):
        shapes = []

        # Calculate grid dimensions
        grid_size = 50  # Base size for grid cells
        cols = (self.width - 2 * padding) // grid_size
        rows = (self.height - 2 * padding) // grid_size

        # Size multipliers
        size_multipliers = [
            1,
            1,
            1,
            1,
            1,
            2,
            2,
            2,
            2,
            3,
        ]  # More 1s, fewer 2s, fewest 3s

        shape_types = ["circle", "square", "triangle"]
        shape_count = 0

        for row in range(int(rows)):
            for col in range(int(cols)):
                if shape_count >= count:
                    break

                # Calculate center position for this grid cell
                x = padding + (col + 0.5) * grid_size
                y = padding + (row + 0.5) * grid_size

                # Choose random shape type and size multiplier
                shape_type = random.choice(shape_types)
                size_mult = random.choice(size_multipliers)
                base_size = grid_size * 0.8  # 80% of grid size

                if random.random() < 0.40:
                    continue
                elif shape_type == "circle":
                    diameter = base_size * size_mult
                    if (
                        x - diameter / 2 >= padding
                        and x + diameter / 2 <= self.width - padding
                        and y - diameter / 2 >= padding
                        and y + diameter / 2 <= self.height - padding
                    ):
                        shapes.append(Shape("circle", x, y, diameter, 0, shape_count))
                        shape_count += 1

                elif shape_type == "square":
                    size = base_size * size_mult
                    if (
                        x - size / 2 >= padding
                        and x + size / 2 <= self.width - padding
                        and y - size / 2 >= padding
                        and y + size / 2 <= self.height - padding
                    ):
                        shapes.append(Shape("square", x, y, size, 0, shape_count))
                        shape_count += 1

                elif shape_type == "triangle":
                    size = base_size * size_mult
                    rotation = random.randint(0, 3) * (math.pi / 2)
                    if (
                        x - size >= padding
                        and x + size <= self.width - padding
                        and y - size >= padding
                        and y + size <= self.height - padding
                    ):
                        shapes.append(
                            Shape("triangle", x, y, size, 0, shape_count, rotation)
                        )
                        shape_count += 1

        return shapes

    def _assign_colors(self):
        for i, shape in enumerate(self.shapes):
            shape.color_index = i % len(self.colors)

    def calculate_unified_color_regions(self):
        """Calculate unified regions for each color, merging all shapes of the same color"""
        # Calculate effective regions first (respecting z-index)
        shape_regions = self.calculate_effective_regions()

        # Group by color_index
        color_regions = {}

        for shape_data in shape_regions:
            color_idx = shape_data["color_index"]
            region = shape_data["region"]

            if color_idx not in color_regions:
                color_regions[color_idx] = []

            color_regions[color_idx].append(region)

        # Merge all regions of the same color
        unified_regions = {}
        for color_idx, regions in color_regions.items():
            if regions:
                try:
                    merged = unary_union(regions)
                    if not merged.is_empty:
                        unified_regions[color_idx] = merged
                except Exception as e:
                    print(f"Error merging regions for color {color_idx}: {e}")
                    # If merge fails, just use the separate regions
                    if regions:
                        unified_regions[color_idx] = regions[0]
                        for r in regions[1:]:
                            try:
                                unified_regions[color_idx] = unified_regions[
                                    color_idx
                                ].union(r)
                            except:
                                pass

        return unified_regions

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

    def generate_global_hatching_lines_enhanced(self):
        """Generate hatching lines with advanced styles: exponential spacing, wavy, or noisy"""
        hatching_lines = {}

        # Get unified color regions
        unified_regions = self.calculate_unified_color_regions()

        # Create global hatching for each color
        for color_idx, region in unified_regions.items():
            # Initialize this color's lines list
            hatching_lines[color_idx] = []

            # Get the hatching pattern for this color
            pattern = self.hatching_patterns[color_idx % len(self.hatching_patterns)]

            # Get style information - add these to your pattern dictionaries
            style = pattern.get(
                "style", "regular"
            )  # Options: "regular", "exponential", "wavy", "noisy"
            exp_factor = pattern.get("exp_factor", 1.5)  # For exponential spacing
            wave_amplitude = pattern.get("wave_amplitude", 5)  # For wavy lines
            wave_frequency = pattern.get("wave_frequency", 0.1)  # For wavy lines
            noise_scale = pattern.get("noise_scale", 0.1)  # For noisy lines
            noise_amplitude = pattern.get("noise_amplitude", 10)  # For noisy lines
            num_points = pattern.get(
                "num_points", 10
            )  # Number of points for wavy/noisy lines

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

                    # Calculate base spacing and number of lines based on style
                    base_spacing = pattern["spacing"]

                    if style == "regular":
                        # Regular evenly-spaced lines
                        spacings = [
                            base_spacing * i
                            for i in range(
                                math.ceil(diagonal_length / base_spacing) * 2
                            )
                        ]
                        start_offset = -diagonal_length / 2

                    elif style == "exponential":
                        # Exponentially increasing spaces between lines
                        spacings = []
                        curr_spacing = base_spacing
                        total_spacing = 0

                        while total_spacing < diagonal_length * 2:
                            spacings.append(total_spacing)
                            curr_spacing *= exp_factor
                            total_spacing += curr_spacing

                        # Add negative spacings for the other side
                        neg_spacings = [-s for s in reversed(spacings) if s > 0]
                        spacings = neg_spacings + spacings
                        start_offset = 0

                    else:  # For wavy and noisy, use regular spacing but modify the lines
                        spacings = [
                            base_spacing * i
                            for i in range(
                                math.ceil(diagonal_length / base_spacing) * 2
                            )
                        ]
                        start_offset = -diagonal_length / 2

                    # Direction vector
                    dir_x = math.cos(angle_rad)
                    dir_y = math.sin(angle_rad)

                    # Generate hatching lines
                    for spacing in spacings:
                        offset = start_offset + spacing

                        # Calculate offset point
                        offset_x = perp_x * offset
                        offset_y = perp_y * offset

                        if style in ["regular", "exponential"]:
                            # Create a straight line
                            start_x = center_x + offset_x - dir_x * diagonal_length
                            start_y = center_y + offset_y - dir_y * diagonal_length
                            end_x = center_x + offset_x + dir_x * diagonal_length
                            end_y = center_y + offset_y + dir_y * diagonal_length

                            hatch_line = LineString(
                                [(start_x, start_y), (end_x, end_y)]
                            )

                        elif style == "wavy":
                            # Create a wavy line with sine wave
                            points = []
                            for i in range(num_points + 1):
                                t = i / num_points
                                # Base point along the line
                                x = (
                                    center_x
                                    + offset_x
                                    + dir_x * (2 * t - 1) * diagonal_length
                                )
                                y = (
                                    center_y
                                    + offset_y
                                    + dir_y * (2 * t - 1) * diagonal_length
                                )

                                # Add wave perpendicular to the line direction
                                wave = (
                                    math.sin(
                                        t * math.pi * 2 * wave_frequency * num_points
                                    )
                                    * wave_amplitude
                                )
                                x += -perp_x * wave
                                y += -perp_y * wave

                                points.append((x, y))

                            hatch_line = LineString(points)

                        elif style == "noisy":
                            # Create a noisy line with Perlin-like noise
                            import random  # Make sure to import this

                            points = []
                            for i in range(num_points + 1):
                                t = i / num_points
                                # Base point along the line
                                x = (
                                    center_x
                                    + offset_x
                                    + dir_x * (2 * t - 1) * diagonal_length
                                )
                                y = (
                                    center_y
                                    + offset_y
                                    + dir_y * (2 * t - 1) * diagonal_length
                                )

                                # Add noise perpendicular to the line direction
                                # Use a simple random noise as a replacement for Perlin noise
                                noise = (random.random() * 2 - 1) * noise_amplitude
                                noise *= noise_scale * diagonal_length

                                x += -perp_x * noise
                                y += -perp_y * noise

                                points.append((x, y))

                            hatch_line = LineString(points)

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
                print(f"Error processing region for color {color_idx}: {e}")
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
            # Add overlapping shapes with same colors to test continuous hatching
            Shape("square", 500, 500, 200, 0, 5),  # Same color as first shape
            Shape("circle", 700, 700, 180, 1, 6),  # Same color as second shape
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
                    # Add interior boundaries (holes)
                    for interior in poly.interiors:
                        interior_coords = list(interior.coords)
                        segments.extend(
                            [
                                (
                                    (interior_coords[i][0], interior_coords[i][1]),
                                    (
                                        interior_coords[i + 1][0],
                                        interior_coords[i + 1][1],
                                    ),
                                )
                                for i in range(len(interior_coords) - 1)
                            ]
                        )

                        # # Add interior boundaries (holes)
                        # for interior in poly.interiors:
                        #     interior_coords = list(interior.coords)
                        #     segments.extend(
                        #         [
                        #             (
                        #                 (interior_coords[i][0], interior_coords[i][1]),
                        #                 (
                        #                     interior_coords[i + 1][0],
                        #                     interior_coords[i + 1][1],
                        #                 ),
                        #             )
                        #             for i in range(len(interior_coords) - 1)
                        #         ]
                        #     )

            return segments

        except Exception as e:
            print(f"Error finding composite outline: {e}")

            # Fallback: return individual shape segments
            segments = []
            for shape in self.shapes:
                segments.extend(shape.get_outline_segments())
            return segments

    def visualize(self, show_hatching=False, figsize=(6, 10)):
        """Visualize the shapes and optionally the hatching patterns"""
        fig, ax = plt.subplots(figsize=figsize)
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
            # Calculate hatching lines using the new global method
            hatching_lines = self.generate_global_hatching_lines_enhanced()

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

    def visualize_unified_color_regions(self, figsize=(6, 10)):
        """Visualize the unified regions for each color"""
        fig, ax = plt.subplots(figsize=figsize)
        ax.set_xlim(0, self.width)
        ax.set_ylim(0, self.height)

        # Draw filled shapes first
        for shape in self.shapes:
            color = self.colors[shape.color_index % len(self.colors)]
            patch = shape.get_matplotlib_patch(color)
            ax.add_patch(patch)

        # Get unified color regions
        unified_regions = self.calculate_unified_color_regions()

        # Draw outlines around unified regions for each color
        outline_colors = ["red", "green", "blue", "orange", "purple"]

        for color_idx, region in unified_regions.items():
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

                        # Add a label in each part
                        centroid = poly.centroid
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

    def export_svg(self, filename=None, figsize=(6, 10)):
        """Export the design as an SVG file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"plotter_hatching_{timestamp}.svg"

        # Calculate global hatching lines
        hatching_lines = self.generate_global_hatching_lines_enhanced()

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


class InteractiveHatchingApp:
    def __init__(self, width=1200, height=1800, num_shapes=40, figsize=(6, 10)):
        self.width = width
        self.height = height
        self.num_shapes = num_shapes
        self.generator = None
        self.fig = None
        self.ax = None
        self.show_hatching = True
        self.show_colors = True
        self.fixed_scenario = False
        self.figsize = figsize

        # Create initial generator
        self.regenerate()

        # Create the figure
        self.setup_figure()

    def regenerate(self):
        """Generate a new composition"""
        self.generator = HatchingGenerator(
            self.width, self.height, self.num_shapes, self.show_colors
        )
        if self.fixed_scenario:
            self.generator.create_fixed_shape_scenario()

    def setup_figure(self):
        """Set up the Matplotlib figure and connect event handlers"""
        self.fig, self.ax = plt.subplots(figsize=self.figsize)

        # Connect event handlers
        self.fig.canvas.mpl_connect("key_press_event", self.on_key_press)

        # Set figure title with instructions
        self.fig.suptitle(
            "Interactive Hatching Generator\n"
            "Press SPACE to generate a new design\n"
            "Press V to save as SVG\n"
            "Press H to toggle hatching\n"
            "Press F to toggle fixed/random scenario\n"
            "Press Q to quit",
            fontsize=14,
        )

        # Initial drawing
        self.update_plot()

    def update_plot(self):
        """Update the plot with current generator data"""
        self.ax.clear()
        self.ax.set_xlim(0, self.width)
        self.ax.set_ylim(0, self.height)

        # Draw shapes
        for shape in self.generator.shapes:
            color = self.generator.colors[
                shape.color_index % len(self.generator.colors)
            ]
            patch = shape.get_matplotlib_patch(color)
            self.ax.add_patch(patch)

        # Calculate and draw the composite outline
        outline_segments = self.generator.find_composite_outline()
        outline_collection = LineCollection(
            outline_segments, colors="black", linewidths=2
        )
        self.ax.add_collection(outline_collection)

        if self.show_colors:
            for shape in self.generator.shapes:
                if shape.color_index == -1:
                    patch.set_facecolor("none")  # Make shape unfilled

        if self.show_hatching:
            # Calculate hatching lines using the global method
            hatching_lines = self.generator.generate_global_hatching_lines_enhanced()

            # Draw hatching lines
            for color_idx, lines in hatching_lines.items():
                line_collection = LineCollection(lines, colors="black", linewidths=0.1)
                self.ax.add_collection(line_collection)

        # Add debug text for each shape (optional)
        # for shape in self.generator.shapes:
        #     self.ax.text(
        #         shape.x,
        #         shape.y,
        #         f"C{shape.color_index}",
        #         ha="center",
        #         va="center",
        #         fontsize=12,
        #         color="white",
        #         fontweight="bold",
        #     )

        self.ax.set_aspect("equal")
        self.ax.axis("off")

        # Add status info
        status_text = f"Mode: {'Fixed' if self.fixed_scenario else 'Random'}, "
        status_text += f"Hatching: {'On' if self.show_hatching else 'Off'}, "
        status_text += f"Shapes: {len(self.generator.shapes)}"
        self.ax.text(
            self.width // 2,
            30,
            status_text,
            ha="center",
            va="center",
            fontsize=14,
            color="black",
            bbox=dict(facecolor="white", alpha=0.8),
        )

        self.fig.tight_layout()
        plt.draw()

    def save_svg(self):
        """Save the current design as an SVG file"""
        downloads_path = os.path.expanduser("~/Downloads")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(downloads_path, f"hatching_{timestamp}.svg")

        saved_file = self.generator.export_svg(filename)

        # Show a message on the plot
        self.ax.text(
            self.width // 2,
            self.height - 30,
            f"Saved to: {os.path.basename(saved_file)}",
            ha="center",
            va="center",
            fontsize=14,
            color="black",
            bbox=dict(facecolor="white", alpha=0.8),
        )
        plt.draw()

        # Clear the message after 2 seconds
        def clear_message():
            self.update_plot()

        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events()

        # Schedule message clearing - note: this won't work in non-interactive mode
        try:
            timer = self.fig.canvas.new_timer(interval=2000)
            timer.add_callback(clear_message)
            timer.start()
        except:
            # If timer doesn't work, just update the plot
            self.update_plot()

    def on_key_press(self, event):
        """Handle key press events"""
        if event.key == " ":  # Spacebar
            self.regenerate()
            self.update_plot()

        elif event.key == "v":  # Save
            self.save_svg()

        elif event.key == "h":  # Toggle hatching
            self.show_hatching = not self.show_hatching
            self.update_plot()

        elif event.key == "c":  # Toggle colors
            self.show_colors = not self.show_colors
            self.update_plot()

        elif event.key == "f":  # Toggle fixed/random scenario
            self.fixed_scenario = not self.fixed_scenario
            self.regenerate()
            self.update_plot()

        elif event.key == "q":  # Quit
            plt.close(self.fig)

    def run(self):
        """Run the application"""
        plt.show()


# Usage example
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate hatched shapes")
    parser.add_argument("--width", type=int, default=1100, help="Width of the canvas")
    parser.add_argument("--height", type=int, default=1700, help="Height of the canvas")
    parser.add_argument(
        "--num-shapes", type=int, default=1000, help="Number of shapes to generate"
    )

    args = parser.parse_args()
    app = InteractiveHatchingApp(
        width=args.width,
        height=args.height,
        num_shapes=args.num_shapes,
    )
    app.run()
