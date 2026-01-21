from pyrevit import forms, revit, DB
import os
import json

try:
    from urllib import quote, unquote # Python 2
except ImportError:
    from urllib.parse import quote, unquote # Python 3

doc = revit.doc

def get_rebar_types():
    collector = DB.FilteredElementCollector(doc).OfClass(DB.Structure.RebarBarType).ToElements()
    return [{"name": t.Name, "id": t.Id.ToString()} for t in collector]

class RebarToolWindow(forms.WPFWindow):
    def __init__(self, xaml_file, html_file):
        forms.WPFWindow.__init__(self, xaml_file)
        self.browser.Navigate(html_file)
        self.browser.LoadCompleted += self.on_load_completed
        self.browser.Navigating += self.on_navigating

    def on_load_completed(self, sender, args):
        try:
            # 1. Prepare Data
            data = get_rebar_types()
            json_str = json.dumps(data)
            safe_str = quote(json_str) # URI Encoded (Safe for JS strings)
            
            # 2. THE FIX: "Eval Injection"
            # Instead of finding the element in Python, we write a line of JS code
            # JS: document.getElementById('data-mailbox').value = '...data...';
            
            js_code = "document.getElementById('data-mailbox').value = '{}';".format(safe_str)
            
            # 3. Run that line of code immediately
            # We use "eval" to run the string as code
            self.browser.InvokeScript("eval", [js_code])
            
            # 4. Now that the mailbox is full, tell JS to read it
            self.browser.InvokeScript("readMailbox")
            
        except Exception as e:
            forms.alert("Error injecting data: " + str(e))
            
    def on_navigating(self, sender, args):
        url = args.Uri.ToString()
        if url.startswith("pyrevit://create_rebar/"):
            args.Cancel = True 
            
            try:
                raw_encoded = url.split("pyrevit://create_rebar/")[1]
                json_data = unquote(raw_encoded)
                user_input = json.loads(json_data)
                
                self.create_rebar_logic(user_input)
                self.Close()
            except Exception as e:
                forms.alert("Decode Error: " + str(e))

    def create_rebar_logic(self, data):
        forms.alert(
            "Success! \n" +
            "Type: " + str(data['rebarId']) + "\n" +
            "Top: " + str(data['top'])
        )

# --- RUN ---
xaml_path = os.path.join(os.path.dirname(__file__), 'ui.xaml')
html_path = os.path.join(os.path.dirname(__file__), 'index.html')

if os.path.exists(xaml_path) and os.path.exists(html_path):
    RebarToolWindow(xaml_path, html_path).ShowDialog()