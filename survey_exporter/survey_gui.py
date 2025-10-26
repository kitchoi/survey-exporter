import tkinter as tk
from tkinter import filedialog, messagebox
import pathlib
from survey_exporter.main import build_survey_responses_html


class SurveyExporterGUI:
    def __init__(self, root):
        self.root = root
        root.title("Survey Exporter")
        
        # API Key
        tk.Label(root, text="API Key:").pack(pady=5)
        self.api_key = tk.Entry(root, width=50)
        self.api_key.pack(pady=5)
        
        # Output Directory
        tk.Label(root, text="Output Directory:").pack(pady=5)
        dir_frame = tk.Frame(root)
        dir_frame.pack(pady=5)
        
        self.output_dir = tk.Entry(dir_frame, width=40)
        self.output_dir.pack(side=tk.LEFT, padx=5)
        
        tk.Button(dir_frame, text="Browse...", command=self.browse_directory).pack(side=tk.LEFT)
        
        # Export Button
        tk.Button(root, text="Export Survey", command=self.export_survey).pack(pady=20)
        
    def browse_directory(self):
        dir_path = filedialog.askdirectory()
        if dir_path:
            self.output_dir.delete(0, tk.END)
            self.output_dir.insert(0, dir_path)
    
    def export_survey(self):
        api_key = self.api_key.get().strip()
        output_dir = self.output_dir.get().strip()
        
        if not api_key:
            messagebox.showerror("Error", "Please enter your API key")
            return
            
        if not output_dir:
            messagebox.showerror("Error", "Please select an output directory")
            return
            
        try:
            build_survey_responses_html(api_key, pathlib.Path(output_dir))
            messagebox.showinfo("Success", 
                              "Survey exported successfully!\n"
                              f"Check {output_dir} for the results.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export survey:\n{str(e)}")

def main():
    root = tk.Tk()
    app = SurveyExporterGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()