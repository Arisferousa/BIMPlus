# -*- coding: utf-8 -*-
"""
BIMPlus Starter Kit (_Starty.py)
General-purpose utilities for pyRevit development across multiple scripts.

Categories:
  - Geometry operations (curves, points, transformations)
  - Face and solid utilities
  - Vector and coordinate transformations
  - Unit conversion helpers
  - Debug visualization
  - Element selection and filtering
"""

from Autodesk.Revit.DB import *
from Autodesk.Revit.UI.Selection import ObjectType
import math
import clr
clr.AddReference("RevitServices")
from pyrevit import revit, HOST_APP, forms

# Global references
doc = HOST_APP.doc
uidoc = HOST_APP.uidoc


# ============================================================================
# UNIT CONVERSION HELPERS
# ============================================================================

def print_unit_to_mm(feet):
    """Convert and print Revit internal units (feet) to millimeters."""
    mm = UnitUtils.ConvertFromInternalUnits(feet, UnitTypeId.Millimeters)
    print("Width (mm): {}".format(mm))

def convert_to_internal_units(value, unit_type):
    """Convert external units to Revit internal units (feet)."""
    return UnitUtils.ConvertToInternalUnits(value, unit_type)


def convert_from_internal_units(value, unit_type):
    """Convert Revit internal units (feet) to external units."""
    return UnitUtils.ConvertFromInternalUnits(value, unit_type)


# ============================================================================
# VECTOR & COORDINATE TRANSFORMATIONS
# ============================================================================

def get_line_local_axes(line, start_pt, end_pt):
    """
    Given a line (or location curve), compute local coordinate axes.
    
    Args:
        line (Line): The reference line.
        start_pt (XYZ): Start point of the line.
        end_pt (XYZ): End point of the line.
    
    Returns:
        tuple: (local_x, local_y, local_z) as XYZ vectors
            - local_x: along the line direction
            - local_y: horizontal perpendicular to line
            - local_z: vertical (usually XYZ.BasisZ)
    """
    # Local X-axis: along the line
    local_x = (end_pt - start_pt).Normalize()

    # Global Z-axis (up)
    global_z = XYZ.BasisZ

    # Local Y-axis: perpendicular to X and Z
    local_y = global_z.CrossProduct(local_x).Normalize()

    # Recompute Z to ensure orthogonality
    local_z = local_x.CrossProduct(local_y).Normalize()

    return local_x, local_y, local_z


def translate_point_along_vector(point, vector, distance):
    """
    Translate a point along a specified vector direction by a given distance.

    Args:
        point (XYZ): Point to translate.
        vector (XYZ): Direction vector (will be normalized).
        distance (float): Distance to move along the vector.

    Returns:
        XYZ: Translated point.
    """
    direction = vector.Normalize()
    translation_vector = direction.Multiply(distance)
    return point + translation_vector


def translate_curve_along_vector(curve, vector, distance):
    """
    Translate a curve along a specified vector direction by a given distance.

    Args:
        curve: A Revit curve to translate.
        vector (XYZ): Direction vector (will be normalized).
        distance (float): Distance to move.

    Returns:
        Translated curve.
    """
    direction = vector.Normalize()
    translation_vector = direction.Multiply(distance)
    transform = Transform.CreateTranslation(translation_vector)
    return curve.CreateTransformed(transform)


def translate_curve_from_point(curve, start_point, end_points):
    """
    Translate a curve from start_point to one or more end_points.
    
    Args:
        curve: A Revit curve to translate.
        start_point (XYZ): Base position of the curve.
        end_points: Single XYZ or list of XYZ points to translate to.

    Returns:
        list: List of translated curves (one per end_point).
    """
    if not isinstance(end_points, list):
        end_points = [end_points]

    translated_curves = []
    for end_pt in end_points:
        translation_vector = end_pt - start_point
        transform = Transform.CreateTranslation(translation_vector)
        translated_curve = curve.CreateTransformed(transform)
        translated_curves.append(translated_curve)

    return translated_curves


def translate_curve_loop(curve_loop, vector, distance):
    """
    Translate an entire CurveLoop along a vector by a given distance.

    Args:
        curve_loop: A Revit CurveLoop object.
        vector (XYZ): Direction vector (will be normalized).
        distance (float): Distance to move.

    Returns:
        CurveLoop: New translated CurveLoop.
    """
    direction = vector.Normalize()
    translation_vector = direction.Multiply(distance)
    transform = Transform.CreateTranslation(translation_vector)

    translated_loop = CurveLoop()
    for curve in curve_loop:
        translated_curve = curve.CreateTransformed(transform)
        translated_loop.Append(translated_curve)

    return translated_loop


def create_line_from_vector(start_point, direction, distance):
    """
    Create a line from a start point, extending in a given direction.

    Args:
        start_point (XYZ): Starting point of the line.
        direction (XYZ): Direction vector (will be normalized).
        distance (float): Length of the line.

    Returns:
        Line: The resulting Revit Line object.
    """
    normalized_direction = direction.Normalize()
    end_point = start_point + normalized_direction * distance
    return Line.CreateBound(start_point, end_point)


# ============================================================================
# LINE DIVISION & PARAMETRIC POINTS
# ============================================================================

def point_on_line_by_params(line, param_list, start, end):
    """
    Get points on a line at normalized parameters (0.0 to 1.0).

    Args:
        line (Line): The reference line.
        param_list (list[float]): Parameters along the line (0.0 to 1.0).
        start (XYZ): Start point of the line.
        end (XYZ): End point of the line.

    Returns:
        list[XYZ]: Points at the specified parameters.
    """
    direction = (end - start).Normalize()
    length = line.Length

    points = []
    for param in param_list:
        point = start + direction * (param * length)
        points.append(point)
    return points


def divide_line_by_parameters(line, params):
    """
    Split a Revit Line into segments based on normalized parameters (0.0 to 1.0).

    Args:
        line (Line): The original Revit line.
        params (list[float]): Parameters along the line (between 0.0 and 1.0), sorted.

    Returns:
        list[Line]: List of Line segments between parameter-defined points.
    
    Raises:
        ValueError: If fewer than 2 parameters are provided.
    """
    if not params or len(params) < 2:
        raise ValueError("At least two parameters are required to split a line.")

    params = sorted(params)
    points = [line.Evaluate(param, True) for param in params]

    segments = []
    for i in range(len(points) - 1):
        segments.append(Line.CreateBound(points[i], points[i + 1]))

    return segments


def divide_lines_by_params(lines, param_list):
    """
    Divide multiple lines using the same parameter list.

    Args:
        lines (list[Line]): Lines to divide.
        param_list (list[float]): Normalized parameters (0.0 to 1.0).

    Returns:
        list[list[Line]]: Segments per line, then per section.
    """
    all_segments = []
    for line in lines:
        segments = divide_line_by_parameters(line, param_list)
        all_segments.append(segments)
    return all_segments


# ============================================================================
# FACE & GEOMETRY UTILITIES
# ============================================================================

def get_normal_from_face(face):
    """
    Compute the average normal of a face at its center.

    Args:
        face: A Revit Face object.

    Returns:
        XYZ: Normalized face normal vector.
    """
    bbox = face.GetBoundingBox()
    center = (bbox.Min + bbox.Max) * 0.5
    return face.ComputeNormal(center).Normalize()


def get_face_width_height(face):
    """
    Measure the two unique side lengths of a planar rectangular face.

    Args:
        face: A planar Face object (assumes rectangular).

    Returns:
        tuple: (width, height) where height >= width.
    
    Raises:
        ValueError: If face is not rectangular or lacks 2 unique edge lengths.
    """
    if not face:
        raise ValueError("Face is None.")

    edge_lengths = []

    # Get the outer edge loop
    for edge_loop in face.EdgeLoops:
        for edge in edge_loop:
            start = edge.AsCurve().GetEndPoint(0)
            end = edge.AsCurve().GetEndPoint(1)
            length = (end - start).GetLength()
            if not any(abs(length - el) < 1e-6 for el in edge_lengths):
                edge_lengths.append(length)

    if len(edge_lengths) != 2:
        raise ValueError("Face is not rectangular (should have exactly 2 unique edge lengths).")

    width, height = sorted(edge_lengths)
    return width, height


def offset_face_loop(face, offset_dist):
    """
    Offset the outer loop of a planar face by a given distance.

    Args:
        face (PlanarFace): A planar face to offset.
        offset_dist (float): Offset distance (negative = inward, positive = outward).

    Returns:
        list[Curve]: List of curves forming the offset loop, suitable for geometry operations.
    
    Raises:
        Exception: If face is not planar or has no edge loops.
    """
    if not isinstance(face, PlanarFace):
        raise Exception("Face must be planar.")

    loops = face.GetEdgesAsCurveLoops()
    if not loops:
        raise Exception("No edge loops found.")
    
    # Usually the largest loop is the outer boundary
    outer_loop = max(loops, key=lambda l: l.GetExactLength())

    normal = face.FaceNormal.Normalize()
    offset_loop = CurveLoop.CreateViaOffset(outer_loop, offset_dist, normal)

    return list(offset_loop)


def get_corners_and_separate_top_bottom(closed_curve):
    """
    Extract corner points from a closed curve loop and separate by Z-coordinate.

    Args:
        closed_curve (list[Curve]): List of curves forming a closed loop.

    Returns:
        tuple: (top_points, bottom_points) - each a list of XYZ points sorted by Z.
    """
    points = []
    for curve in closed_curve:
        start_pt = curve.GetEndPoint(0)
        end_pt = curve.GetEndPoint(1)
        points.append(start_pt)
        points.append(end_pt)

    # Remove duplicates
    unique_points = []
    tol = 1e-9
    for pt in points:
        if not any((pt - up).IsAlmostEqualTo(XYZ(0, 0, 0), tol) for up in unique_points):
            unique_points.append(pt)

    # Sort by Z coordinate
    unique_points.sort(key=lambda p: p.Z)

    # Assuming rectangular, split into bottom (lowest 2) and top (highest 2)
    bottom_points = unique_points[:2]
    top_points = unique_points[-2:]

    return top_points, bottom_points


# ============================================================================
# ELEMENT SELECTION & FILTERING
# ============================================================================

def get_element_by_name(doc, element_class, target_name):
    """
    Find an element by class and name.

    Args:
        doc: Revit document.
        element_class: Class to filter (e.g., RebarBarType, FamilySymbol).
        target_name (str): Name of the element to find.

    Returns:
        Element or None if not found.
    """
    collector = FilteredElementCollector(doc).OfClass(element_class)
    for elem in collector:
        name = Element.Name.GetValue(elem)
        if name == target_name:
            return elem
    return None


def get_bar_type_by_name(doc, target_name):
    """Get a RebarBarType by name."""
    return get_element_by_name(doc, RebarBarType, target_name)


def get_hook_type_by_name(doc, name):
    """Get a RebarHookType by name."""
    return get_element_by_name(doc, RebarHookType, name)


def get_elements_of_category(doc, category):
    """
    Get all elements in a specific category.

    Args:
        doc: Revit document.
        category (BuiltInCategory): Category to filter.

    Returns:
        list: Filtered elements (excludes types).
    """
    return list(FilteredElementCollector(doc).OfCategory(category).WhereElementIsNotElementType())


# ============================================================================
# DEBUG VISUALIZATION
# ============================================================================

def visualize_point(doc, point, size=0.1, name="PointMarker"):
    """
    Visualize a point as a small cross using DirectShape.

    Args:
        doc: Revit document.
        point (XYZ): Point to visualize.
        size (float): Size of the cross in drawing units.
        name (str): Tag name for the DirectShape.

    Returns:
        DirectShape: The created visualization element.
    """
    try:
        t = Transaction(doc, "Visualize Point")
        t.Start()
        
        half = size / 2
        x_axis = XYZ(half, 0, 0)
        y_axis = XYZ(0, half, 0)

        line1 = Line.CreateBound(point - x_axis, point + x_axis)
        line2 = Line.CreateBound(point - y_axis, point + y_axis)

        ds = DirectShape.CreateElement(doc, ElementId(BuiltInCategory.OST_GenericModel))
        ds.ApplicationId = name
        ds.SetShape([line1, line2])
        
        t.Commit()
        return ds
    except Exception as e:
        print("Error visualizing point: {}".format(e))
        if t.HasStarted():
            t.RollBack()
        return None


def visualize_vector_directshape(doc, origin, direction, scale_mm=500, name="VectorDebug"):
    """
    Visualize a vector as a line using DirectShape (with transaction).

    Args:
        doc: Revit document.
        origin (XYZ): Start point of vector.
        direction (XYZ): Direction vector (will be normalized).
        scale_mm (float): Length of vector in millimeters.
        name (str): Tag name for the DirectShape.

    Returns:
        DirectShape: The created visualization element, or None on error.
    """
    try:
        length_ft = UnitUtils.ConvertToInternalUnits(scale_mm, UnitTypeId.Millimeters)
        end = origin + direction.Normalize().Multiply(length_ft)
        line = Line.CreateBound(origin, end)

        t = Transaction(doc, "Visualize Vector")
        t.Start()

        ds = DirectShape.CreateElement(doc, ElementId(BuiltInCategory.OST_GenericModel))
        ds.ApplicationId = name
        ds.SetShape([line])

        t.Commit()
        return ds

    except Exception as e:
        print("Error creating debug vector shape: {}".format(e))
        return None


def visualize_vector_directshape_no_trans(doc, origin, direction, scale_mm=500, name="VectorDebug"):
    """
    Visualize a vector as a line using DirectShape (without transaction).
    Use when already inside a transaction.

    Args:
        doc: Revit document.
        origin (XYZ): Start point of vector.
        direction (XYZ): Direction vector (will be normalized).
        scale_mm (float): Length of vector in millimeters.
        name (str): Tag name for the DirectShape.

    Returns:
        DirectShape: The created visualization element, or None on error.
    """
    try:
        length_ft = UnitUtils.ConvertToInternalUnits(scale_mm, UnitTypeId.Millimeters)
        end = origin + direction.Normalize().Multiply(length_ft)
        line = Line.CreateBound(origin, end)

        ds = DirectShape.CreateElement(doc, ElementId(BuiltInCategory.OST_GenericModel))
        ds.ApplicationId = name
        ds.SetShape([line])

        return ds

    except Exception as e:
        print("Error creating debug vector shape: {}".format(e))
        return None


def visualize_edges(doc, curves, name="DebugEdges"):
    """
    Visualize a collection of curves using DirectShape (with transaction).

    Args:
        doc: Revit document.
        curves (list[Curve]): Curves to visualize.
        name (str): Tag name for the DirectShape.
    """
    try:
        t = Transaction(doc, "Visualize Edges")
        t.Start()

        ds = DirectShape.CreateElement(doc, ElementId(BuiltInCategory.OST_GenericModel))
        ds.ApplicationId = name
        ds.SetShape(curves)

        t.Commit()
    except Exception as e:
        print("Error visualizing edges: {}".format(e))
        if t.HasStarted():
            t.RollBack()


def visualize_edges_no_trans(doc, curves, name="DebugEdges"):
    """
    Visualize a collection of curves using DirectShape (without transaction).
    Use when already inside a transaction.

    Args:
        doc: Revit document.
        curves (list[Curve]): Curves to visualize.
        name (str): Tag name for the DirectShape.
    """
    try:
        ds = DirectShape.CreateElement(doc, ElementId(BuiltInCategory.OST_GenericModel))
        ds.ApplicationId = name
        ds.SetShape(curves)

    except Exception as e:
        print("Error visualizing edges: {}".format(e))


def visualize_face_outline(doc, face, name="FaceOutline"):
    """
    Visualize the outline edges of a face.

    Args:
        doc: Revit document.
        face: A Face object.
        name (str): Tag name for visualization.
    """
    edges = face.GetEdgesAsCurveLoops()
    if edges:
        visualize_edges(doc, list(edges[0]), name=name)


# ============================================================================
# VALIDATION UTILITIES
# ============================================================================

def validate_layout_lengths(parameter, default_tie=None, **kwargs):
    """
    Validate that all layout lists match the parameter list length.

    Args:
        parameter (list): Reference list (usually parameters).
        default_tie (list, optional): Tie layout list to validate.
        **kwargs: Named layout lists to validate.

    Raises:
        ValueError: If any layout list length doesn't match expected sections.
    """
    expected_sections = len(parameter) - 1
    errors = []

    # Check length of layout lists
    for name, values in kwargs.items():
        if len(values) != expected_sections:
            errors.append("  Layout '{}': expected {}, got {}".format(name, expected_sections, len(values)))

    # Check tie layout validity
    if default_tie is not None:
        if len(default_tie) != expected_sections:
            errors.append("  Tie layout: expected {}, got {}".format(expected_sections, len(default_tie)))

    if errors:
        raise ValueError("Layout validation failed:\n" + "\n".join(errors))


def is_closed_loop(curve_loop, tolerance=1e-6):
    """
    Check if a CurveLoop is properly closed.

    Args:
        curve_loop: A Revit CurveLoop object.
        tolerance (float): Tolerance for point comparison.

    Returns:
        bool: True if the loop is closed, False otherwise.
    """
    curves = list(curve_loop)
    if not curves:
        return False

    for i in range(len(curves)):
        current_end = curves[i].GetEndPoint(1)
        next_start = curves[(i + 1) % len(curves)].GetEndPoint(0)
        if not current_end.IsAlmostEqualTo(next_start, tolerance):
            return False
    return True


# ============================================================================
# END OF STARTER KIT
# ============================================================================
