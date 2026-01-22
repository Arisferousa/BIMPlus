from pyrevit import forms
import os.path as op

class DockPanel(forms.WPFPanel):
    panel_title:str = "Contextual Panel"
    panel_id:str = "pyrevit.contextual.panel"
    panel_source = op.join(op.dirname(__file__), "ContextualDock.xaml")

    def do_something(self, sender, args):
        forms.alert("Hello from Contextual Dockable Panel!")

if not forms.is_registered_dockable_panel(DockPanel):
    forms.register_dockable_panel(DockPanel)
    