
from pyrevit import HOST_APP
from pyrevit.revit.db.transaction import Transaction as pyTransaction
from pyrevit.revit.selection import pick_element

import sys
from Autodesk.Revit.DB import *
from Autodesk.Revit.UI.Selection import ObjectType

# Get the current document and selection
uidoc = HOST_APP.uidoc
doc = HOST_APP.doc
selection = uidoc.Selection

if selection.GetElementIds().Count == 0:
    print("No element selected")
    sys.exit()

element = doc.GetElement(selection.GetElementIds()[0])

# Check if element is a Wall and has CurtainGrid
if not isinstance(element, Wall):
    print("Selected element is not a wall")
    sys.exit()

curtain_grid = element.CurtainGrid
if curtain_grid is None:
    print("Selected wall is not a curtain wall")
    sys.exit()

# Extract curtain wall data
curtain_data = {
    "Type Name": element.get_Parameter(BuiltInParameter.ELEM_TYPE_PARAM).AsValueString(),
    "Base Constraint": element.get_Parameter(BuiltInParameter.WALL_BASE_CONSTRAINT).AsElementId(),
    "Base Offset": element.get_Parameter(BuiltInParameter.WALL_BASE_OFFSET).AsString(),
    "Top Constraint": element.get_Parameter(BuiltInParameter.WALL_HEIGHT_TYPE).AsElementId(),
    "Unconnected Height": element.get_Parameter(BuiltInParameter.WALL_USER_HEIGHT_PARAM).AsDouble(),
    "Length": element.get_Parameter(BuiltInParameter.CURVE_ELEM_LENGTH).AsDouble(),
    "Curtain_U Grid Lines": curtain_grid.GetUGridLineIds().Count,
    "Curtain_V Grid Lines": curtain_grid.GetVGridLineIds().Count
}

# print("Curtain Wall Data (m):")
# for key, value in curtain_data.items():
#     if isinstance(value, float):
#         value = UnitUtils.ConvertFromInternalUnits(value, UnitTypeId.Meters)
#     print("{}: {}".format(key, value))

with pyTransaction("Move Curtain Wall"):
    copied_wall_id = ElementTransformUtils.CopyElement(doc, element.Id, XYZ(10, 0, 0))[0]
    ElementTransformUtils.RotateElement(doc, copied_wall_id, Line.CreateBound(XYZ(10, 0, 0), XYZ(10, 0, 10)), 3.14159 / 4)  # Rotate 45 degrees
# Prompt to pick object
picked_element = pick_element("Pick an object")

copied_wall = doc.GetElement(copied_wall_id)
copied_wall_curve = picked_element.Location.Curve
copied_wall_curve = copied_wall.Location.Curve

