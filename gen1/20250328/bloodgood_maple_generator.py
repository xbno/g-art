import numpy as np
import random
import math
import svgwrite
from shapely.geometry import Point, LineString, Polygon
from shapely.ops import unary_union
from datetime import datetime
import os


class BloodgoodMapleGenerator:
    def __init__(self, width=800, height=1000, branch_iterations=7):
        self.width = width
        self.height = height
        self.branch_iterations = branch_iterations
        # Deep burgundy red for Bloodgood maple
        self.leaf_color = "#8B0000"
        self.branch_color = "#1A0F0B"
        self.trunk_width_base = 20
        self.trunk_height = height * 0.3
        self.trunk_start_y = height * 0.8

        # The root of our tree (trunk base)
        self.root_x = width // 2
        self.root_y = self.trunk_start_y

        # Dictionary to store all branches as LineStrings
        self.branches = {}
        self.branch_id = 0

        # Store leaf positions
        self.leaf_positions = []
        self.leaf_sizes = []

        # Store the overall tree silhouette polygon
        self.tree_silhouette = None

    def generate_trunk(self):
        """Generate the main trunk of the tree"""
        # Add some curvature to the trunk
        curve_factor = self.width * 0.05
        mid_x = self.root_x + random.uniform(-curve_factor, curve_factor)

        # Create trunk control points
        points = [
            (self.root_x, self.root_y),
            (mid_x, self.root_y - self.trunk_height * 0.5),
            (self.root_x, self.root_y - self.trunk_height),
        ]

        # Create LineString for trunk
        trunk = LineString(points)
        self.branches[self.branch_id] = {
            "line": trunk,
            "width": self.trunk_width_base,
            "level": 0,
            "parent": None,
        }
        self.branch_id += 1

        return trunk

    def generate_branch(self, start_point, direction, length, width, level):
        """Generate a branch starting from start_point in the given direction"""
        # Add some randomness to angle and length
        angle_variation = math.pi / 6  # 30 degrees
        angle = direction + random.uniform(-angle_variation, angle_variation)

        # Adjust length with some randomness
        length_variation = 0.2  # 20%
        adjusted_length = length * (
            1 + random.uniform(-length_variation, length_variation)
        )

        # Calculate end point
        end_x = start_point[0] + adjusted_length * math.cos(angle)
        end_y = start_point[1] + adjusted_length * math.sin(angle)

        # Add some curvature
        curve_factor = length * 0.3
        mid_x = (start_point[0] + end_x) / 2 + random.uniform(
            -curve_factor, curve_factor
        )
        mid_y = (start_point[1] + end_y) / 2 + random.uniform(
            -curve_factor, curve_factor
        )

        # Create control points for the branch
        points = [start_point, (mid_x, mid_y), (end_x, end_y)]

        # Create LineString for branch
        branch = LineString(points)

        # Store branch in our dictionary
        branch_id = self.branch_id
        self.branches[branch_id] = {
            "line": branch,
            "width": width,
            "level": level,
            "parent": None,
        }
        self.branch_id += 1

        return branch, (end_x, end_y)

    def recursive_branch(self, parent_id, start_point, direction, length, width, level):
        """Recursively generate branches"""
        if level >= self.branch_iterations:
            # Add leaves at the end of branches
            self.add_leaf(start_point, level)
            return

        # Generate the current branch
        branch, end_point = self.generate_branch(
            start_point, direction, length, width, level
        )
        current_id = self.branch_id - 1

        # Update parent reference
        self.branches[current_id]["parent"] = parent_id

        # Determine how many child branches to create
        if level < 3:
            num_branches = random.randint(2, 3)
        else:
            num_branches = random.randint(1, 2)

        # Create child branches
        for i in range(num_branches):
            # Branch direction (upwards with some spread)
            if i == 0:
                # First branch continues somewhat in the same direction
                new_direction = direction + random.uniform(-math.pi / 4, math.pi / 4)
            else:
                # Other branches spread more
                if random.random() < 0.5:
                    new_direction = direction + random.uniform(math.pi / 4, math.pi / 2)
                else:
                    new_direction = direction + random.uniform(
                        -math.pi / 2, -math.pi / 4
                    )

            # Branch length decreases with level
            new_length = length * (0.6 + random.uniform(0, 0.2))
            # Branch width decreases with level
            new_width = width * 0.7

            # Create the branch recursively
            self.recursive_branch(
                current_id, end_point, new_direction, new_length, new_width, level + 1
            )

            # Add some leaves at branch joints for mid-level branches
            if level >= 2 and random.random() < 0.7:
                self.add_leaf(end_point, level)

    def add_leaf(self, position, level):
        """Add a leaf at the given position"""
        # Leaf size decreases with branch level
        base_size = 20 - level
        size = max(base_size * (0.8 + random.uniform(0, 0.4)), 5)

        self.leaf_positions.append(position)
        self.leaf_sizes.append(size)

    def generate_tree(self):
        """Generate the entire tree structure"""
        # Generate trunk
        trunk = self.generate_trunk()
        trunk_end = list(trunk.coords)[-1]

        # Initial branches from the top of the trunk
        num_initial_branches = random.randint(3, 5)

        for i in range(num_initial_branches):
            # Direction upwards with spread
            direction = -math.pi / 2 + random.uniform(-math.pi / 4, math.pi / 4)

            # Initial branch length proportional to trunk height
            length = self.trunk_height * (0.5 + random.uniform(0, 0.3))

            # Initial branch width proportional to trunk width
            width = self.trunk_width_base * 0.6

            # Create branch recursively
            self.recursive_branch(0, trunk_end, direction, length, width, 1)

    def create_leaf_shape(self, position, size):
        """Create a maple leaf shape at the given position"""
        # Simplified maple leaf shape (5-lobed leaf)
        angle_offset = random.uniform(0, 2 * math.pi)  # Random rotation

        lobes = 5
        points = []

        for i in range(10):  # 10 points to create 5 lobes (peak and valley for each)
            angle = angle_offset + (2 * math.pi * i) / 10
            radius = size

            if i % 2 == 0:  # Lobe peaks
                radius *= 0.8 + random.uniform(0, 0.4)
            else:  # Valleys between lobes
                radius *= 0.3 + random.uniform(0, 0.2)

            x = position[0] + radius * math.cos(angle)
            y = position[1] + radius * math.sin(angle)
            points.append((x, y))

        return Polygon(points)

    def create_tree_silhouette(self):
        """Create the overall tree silhouette by combining leaves"""
        leaf_shapes = []

        # Create individual leaf shapes
        for i, pos in enumerate(self.leaf_positions):
            size = self.leaf_sizes[i]
            leaf = self.create_leaf_shape(pos, size)
            leaf_shapes.append(leaf)

        # Create clusters of leaves at the end of branches to form a dense canopy
        for branch_id, branch_data in self.branches.items():
            if (
                branch_data["level"] >= 3
            ):  # Only add leaf clusters to higher level branches
                line = branch_data["line"]
                end_point = list(line.coords)[-1]

                # Add a cluster of leaves
                cluster_size = (
                    30 - branch_data["level"] * 2
                )  # Smaller clusters on higher levels
                num_leaves = random.randint(3, 7)

                for _ in range(num_leaves):
                    offset_x = random.uniform(-cluster_size, cluster_size)
                    offset_y = random.uniform(-cluster_size, cluster_size)
                    leaf_pos = (end_point[0] + offset_x, end_point[1] + offset_y)
                    leaf_size = random.uniform(10, 20)
                    leaf = self.create_leaf_shape(leaf_pos, leaf_size)
                    leaf_shapes.append(leaf)

        # Combine all leaf shapes to form the tree silhouette
        if leaf_shapes:
            self.tree_silhouette = unary_union(leaf_shapes)
        else:
            # Fallback if no leaves were generated
            self.tree_silhouette = Polygon(
                [(self.width / 2, 0), (0, self.height), (self.width, self.height)]
            )

    def export_svg(self, filename=None):
        """Export the tree as an SVG file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"bloodgood_maple_{timestamp}.svg"

        # Create SVG
        dwg = svgwrite.Drawing(
            filename, size=(f"{self.width}px", f"{self.height}px"), profile="tiny"
        )

        # Create groups for different parts
        branches_group = dwg.add(dwg.g(id="branches"))
        leaves_group = dwg.add(dwg.g(id="leaves"))

        # Add trunk and branches
        for branch_id, branch_data in self.branches.items():
            line = branch_data["line"]
            coords = list(line.coords)

            # Calculate stroke width based on branch level
            width = branch_data["width"] * (1.1 - branch_data["level"] * 0.1)
            width = max(width, 1)  # Minimum width

            # Create path
            path = dwg.path(d=f"M{coords[0][0]},{coords[0][1]}")
            for point in coords[1:]:
                path.push(f"L{point[0]},{point[1]}")

            path.stroke(self.branch_color, width=width)
            path.fill("none")
            branches_group.add(path)

        # Add tree silhouette (leaves)
        if self.tree_silhouette is not None:
            if self.tree_silhouette.geom_type == "Polygon":
                exterior_coords = list(self.tree_silhouette.exterior.coords)
                # Convert coordinates to proper format for svgwrite
                points = [(x, y) for x, y in exterior_coords]
                leaves_group.add(dwg.polygon(points=points, fill=self.leaf_color))

                # Add any holes in the silhouette
                for interior in self.tree_silhouette.interiors:
                    interior_coords = list(interior.coords)
                    points = [(x, y) for x, y in interior_coords]
                    leaves_group.add(dwg.polygon(points=points, fill="white"))

            elif self.tree_silhouette.geom_type == "MultiPolygon":
                for poly in self.tree_silhouette.geoms:
                    exterior_coords = list(poly.exterior.coords)
                    points = [(x, y) for x, y in exterior_coords]
                    leaves_group.add(dwg.polygon(points=points, fill=self.leaf_color))

                    # Add any holes in the polygon
                    for interior in poly.interiors:
                        interior_coords = list(interior.coords)
                        points = [(x, y) for x, y in interior_coords]
                        leaves_group.add(dwg.polygon(points=points, fill="white"))

        # Save SVG
        dwg.save()
        print(f"SVG saved to {filename}")
        return filename


def generate_bloodgood_maple(width=800, height=1000, iterations=7, output_file=None):
    """
    Generate a Japanese Bloodgood Maple tree silhouette as SVG

    Parameters:
    width (int): Width of the SVG canvas
    height (int): Height of the SVG canvas
    iterations (int): Number of branch iterations, higher values create more detailed trees
    output_file (str): Output filename (will generate a timestamped name if None)

    Returns:
    str: Path to the saved SVG file
    """
    generator = BloodgoodMapleGenerator(width, height, iterations)
    generator.generate_trunk()
    generator.generate_tree()
    generator.create_tree_silhouette()
    return generator.export_svg(output_file)


if __name__ == "__main__":
    # Generate a tree with default parameters
    output_file = generate_bloodgood_maple(width=800, height=1000, iterations=6)
    print(f"Generated tree saved to: {output_file}")

    # Uncomment below to generate multiple trees with different parameters
    """
    for i in range(5):
        width = random.randint(700, 900)
        height = random.randint(900, 1100)
        iterations = random.randint(5, 7)
        output_file = generate_bloodgood_maple(
            width=width, 
            height=height, 
            iterations=iterations,
            output_file=f"bloodgood_tree_variant_{i+1}.svg"
        )
        print(f"Generated variant {i+1} saved to: {output_file}")
    """
