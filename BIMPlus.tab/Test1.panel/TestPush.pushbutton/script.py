from __future__ import print_function
import os
import sys
import math
import _Starty as starty
from pyrevit import forms, revit, HOST_APP
from Autodesk.Revit.DB import *
from Autodesk.Revit.UI.Selection import ObjectType

# filepath: c:/Users/Alvin/Documents/GitHub/BIMPlus/BIMPlus.tab/Test1.panel/TestPush.pushbutton/script.py
# Prototype Rebar Generator (beam-first) - first-pass implementation
# Uses DirectShape preview geometry. Replace DirectShape with Rebar.Create* calls when ready.

# Ensure local lib is importable (relative to this script location -> repo root /lib)
this_dir = os.path.dirname(__file__)
repo_root = os.path.normpath(os.path.join(this_dir, '..', '..', '..'))
lib_dir = os.path.join(repo_root, 'lib')
if lib_dir not in sys.path:
    sys.path.append(lib_dir)

doc = HOST_APP.doc
uidoc = HOST_APP.uidoc

# -----------------------
# Small helper functions
# -----------------------
def to_internal_mm(mm_val):
    return UnitUtils.ConvertToInternalUnits(mm_val, UnitTypeId.Millimeters)
def safe_int(val, default=0):
    try:
        return int(val)
    except:
        return default

def safe_float(val, default=0.0):
    try:
        return float(val)
    except:
        return default

# -----------------------
# User inputs (simple form)
# -----------------------
scope = forms.ask_for_one_item(
    ["selected", "all_of_type"],
    default="selected",
    message="Target scope"
)


# Minimal numeric inputs
top_count = safe_int(forms.ask_for_string("Top layer count (integer)", default="2"))
bottom_count = safe_int(forms.ask_for_string("Bottom layer count (integer)", default="2"))
cover_mm = safe_float(forms.ask_for_string("Concrete cover (mm)", default="30"))
long_dia_mm = safe_float(forms.ask_for_string("Longitudinal bar diameter (mm)", default="16"))
stirrup_dia_mm = safe_float(forms.ask_for_string("Stirrup diameter (mm)", default="8"))
stirrup_spacing_mm = safe_float(forms.ask_for_string("Stirrup spacing (mm)", default="150"))
preview_only = forms.ask_for_one_item(["yes", "no"], default="yes", message="Preview only?") == "yes"


# Resolve targets
targets = []
if scope == "selected":
    sel_ids = uidoc.Selection.GetElementIds()
    if not sel_ids:
        forms.alert("No elements selected. Select beam instance(s) and re-run.", title="Selection required")
        sys.exit()
    for eid in sel_ids:
        e = doc.GetElement(eid)
        if e is not None:
            targets.append(e)
else:  # all_of_type
    # Ask user to pick one representative beam instance to determine FamilySymbol
    try:
        ref = uidoc.Selection.PickObject(ObjectType.Element, "Pick one instance of beam family/type to apply to all instances")
    except Exception:
        forms.alert("No element picked. Aborting.", title="Cancelled")
        sys.exit()
    picked = doc.GetElement(ref.ElementId)
    if picked is None:
        forms.alert("Picked element not found. Aborting.")
        sys.exit()
    sym = picked.Symbol
    # Collect all instances of same FamilySymbol
    col = FilteredElementCollector(doc).OfClass(FamilyInstance).WhereElementIsNotElementType()
    for inst in col:
        try:
            if inst.Symbol.Id == sym.Id:
                targets.append(inst)
        except Exception:
            pass

if not targets:
    forms.alert("No target beams found. Aborting.")
    sys.exit()

# -----------------------
# Core: build preview geometry per beam
# -----------------------
all_debug_shapes = []
for host in targets:
    # Get location line
    loc = host.Location
    if not isinstance(loc, LocationCurve):
        print("Skipping host (no LocationCurve): {}".format(host.Id))
        continue
    curve = loc.Curve
    start_pt = curve.GetEndPoint(0)
    end_pt = curve.GetEndPoint(1)

    # Rough section extents via bounding box (model coordinates)
    bbox = host.get_BoundingBox(None)
    if bbox is None:
        print("Skipping host (no bbox): {}".format(host.Id))
        continue
    size_x = abs(bbox.Max.X - bbox.Min.X)
    size_y = abs(bbox.Max.Y - bbox.Min.Y)
    size_z = abs(bbox.Max.Z - bbox.Min.Z)
    # Heuristic: treat size_x as beam width, size_z as depth (vertical)
    beam_width = max(size_x, size_y)  # best-effort
    beam_depth = size_z if size_z > 1e-6 else max(size_x, size_y)

    # local axes along beam
    local_x, local_y, local_z = starty.get_line_local_axes(curve, start_pt, end_pt)

    # Convert covers/diameters to internal units
    cover_ft = to_internal_mm(cover_mm)
    long_rad = to_internal_mm(long_dia_mm) * 0.5
    stirrup_rad = to_internal_mm(stirrup_dia_mm) * 0.5

    # compute offsets from centroid (approx)
    half_depth = beam_depth / 2.0
    z_offset_top = (half_depth - cover_ft - long_rad)
    z_offset_bot = -(half_depth - cover_ft - long_rad)

    # compute across-width distribution for bars (centered)
    usable_width = beam_width - 2 * cover_ft - 2 * long_rad
    def compute_offsets(count):
        if count <= 0:
            return []
        if count == 1:
            return [0.0]
        step = usable_width / (count - 1) if count > 1 else 0.0
        start = -usable_width / 2.0
        return [start + i * step for i in range(count)]

    top_offsets = compute_offsets(top_count)
    bot_offsets = compute_offsets(bottom_count)

    # Build line curves for each bar (as centerline)
    bar_curves = []
    for off in top_offsets:
        offset_vec = local_y.Multiply(off) + local_z.Multiply(z_offset_top)
        sp = start_pt + offset_vec
        ep = end_pt + offset_vec
        bar_curves.append(Line.CreateBound(sp, ep))

    for off in bot_offsets:
        offset_vec = local_y.Multiply(off) + local_z.Multiply(z_offset_bot)
        sp = start_pt + offset_vec
        ep = end_pt + offset_vec
        bar_curves.append(Line.CreateBound(sp, ep))

    # Stirrup locations along beam length: simple uniform spacing from start+end cover to end-cover
    start_cover = cover_ft + stirrup_rad + 0.05  # small margin
    end_cover = cover_ft + stirrup_rad + 0.05
    beam_length = curve.Length
    usable_length = max(0.0, beam_length - start_cover - end_cover)
    if usable_length <= 0:
        stirrup_locations = []
    else:
        spacing_ft = to_internal_mm(stirrup_spacing_mm)
        count = int(math.floor(usable_length / spacing_ft)) + 1
        # compute param positions along curve (normalized)
        stirrup_locations = []
        for i in range(count):
            dist_along = start_cover + min(i * spacing_ft, usable_length)
            t = dist_along / beam_length
            p = curve.Evaluate(t, True)
            stirrup_locations.append(p)

    # Create simple rectangular stirrup curves (closed) in local Y-Z plane and oriented to local_x
    stirrup_curves = []
    stirrup_half_w = (beam_width / 2.0) - cover_ft - stirrup_rad
    stirrup_half_d = (beam_depth / 2.0) - cover_ft - stirrup_rad
    if stirrup_half_w > 1e-6 and stirrup_half_d > 1e-6:
        for locpt in stirrup_locations:
            # define 4 corner points in local coordinates
            p1 = locpt + local_y.Multiply(-stirrup_half_w) + local_z.Multiply(-stirrup_half_d)
            p2 = locpt + local_y.Multiply(stirrup_half_w) + local_z.Multiply(-stirrup_half_d)
            p3 = locpt + local_y.Multiply(stirrup_half_w) + local_z.Multiply(stirrup_half_d)
            p4 = locpt + local_y.Multiply(-stirrup_half_w) + local_z.Multiply(stirrup_half_d)
            # create 4 edges as lines (closed loop)
            l1 = Line.CreateBound(p1, p2)
            l2 = Line.CreateBound(p2, p3)
            l3 = Line.CreateBound(p3, p4)
            l4 = Line.CreateBound(p4, p1)
            stirrup_curves.append(l1)
            stirrup_curves.append(l2)
            stirrup_curves.append(l3)
            stirrup_curves.append(l4)
    # collect shapes (bars in one set, stirrups separate)
    all_debug_shapes.append((bar_curves, "Preview_Longitudinal_Bars_{}".format(host.Id)))
    if stirrup_curves:
        all_debug_shapes.append((stirrup_curves, "Preview_Stirrups_{}".format(host.Id)))

# -----------------------
# Visualization / Creation
# -----------------------
for curves, name in all_debug_shapes:
    # For preview or apply we use DirectShape wrapper functions from _Starty (they handle transactions)
    if preview_only:
        starty.visualize_edges(doc, curves, name=name)
    else:
        # Apply path currently also uses DirectShape (placeholder for true Rebar creation)
        starty.visualize_edges(doc, curves, name="Applied_" + name)

# Summary
forms.alert(
    "Prototype run complete.\nTargets: {}\nCreated preview shapes: {}\nNote: This prototype creates DirectShape geometry as preview/applied geometry.\nReplace DirectShape with Rebar.Create* calls when ready.".format(
        len(targets), len(all_debug_shapes)
    ),
    title="Done"
)