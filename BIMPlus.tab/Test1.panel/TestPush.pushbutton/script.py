# coding: utf8
# noinspection PyUnresolvedReferences

from pyrevit import HOST_APP
from pyrevit import forms
from event import CustomizableEvent

uidoc = __revit__.ActiveUIDocument # type: ignore
app = HOST_APP.app
uiapp = HOST_APP.uiapp
doc = uidoc.Document
activeView = doc.ActiveView


#--- FUNCTIONS ---#
def get_elements():
    try:
        selected_elements = [doc.GetElement(id) for id in uidoc.Selection.GetElementIds()]
        for elem in selected_elements:
            forms.alert("ID: {}, Name: {}".format(elem.Id, elem.Name))
    except Exception as e:
        print("Error retrieving elements: {}".format(e))


# #--- IExternalEventHandler ---#
customizable_event = CustomizableEvent()

#--- MAIN ---#
class DockPanel_ViewDebugger(forms.WPFWindow):
    def __init__(self, xaml_source):
        forms.WPFWindow.__init__(self, xaml_source)
        self.Show() 
        self.TitleText.Text = "Debug Window"

    def do_something(self, sender, e):
        customizable_event.raise_event(get_elements)

#--- RUN ---#
debug_window = DockPanel_ViewDebugger('ContextualDock.xaml')