import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import pathlib
import queue
import threading
from survey_exporter.main import build_survey_responses_html


class SurveyExporterGUI:
    def __init__(self, root):
        self.root = root
        root.title("Survey Exporter")
        
        # API Key
        tk.Label(root, text="Password:").pack(pady=5)
        self.api_key = tk.Entry(root, width=50, show="*")
        self.api_key.pack(pady=5)
        
        # Output Directory
        tk.Label(root, text="Output Directory:").pack(pady=5)
        dir_frame = tk.Frame(root)
        dir_frame.pack(pady=5)
        
        self.output_dir = tk.Entry(dir_frame, width=40)
        self.output_dir.pack(side=tk.LEFT, padx=5)
        
        tk.Button(dir_frame, text="Browse...", command=self.browse_directory).pack(side=tk.LEFT)
        
        # Output Console
        tk.Label(root, text="Output:").pack(pady=5)
        self.console = scrolledtext.ScrolledText(root, height=10, width=60)
        self.console.pack(pady=5, padx=5, fill=tk.BOTH, expand=True)
        
        # Export Button
        tk.Button(root, text="Export Survey", command=self.export_survey).pack(pady=20)

        # Setup stdout redirection
        self.output_queue = queue.Queue()
        
        # Start output monitoring
        self.monitor_output()
        
    def monitor_output(self):
        """Check queue for new output and display it"""
        while True:
            try:
                text = self.output_queue.get_nowait()
                self.console.insert(tk.END, text + "\n")
                self.console.see(tk.END)
                self.console.update_idletasks()
            except queue.Empty:
                break
        self.root.after(100, self.monitor_output)

    def browse_directory(self):
        dir_path = filedialog.askdirectory()
        if dir_path:
            self.output_dir.delete(0, tk.END)
            self.output_dir.insert(0, dir_path)
    
    def export_survey(self):
        # Clear previous output
        self.console.delete(1.0, tk.END)
        
        api_key = self.api_key.get().strip()
        output_dir = self.output_dir.get().strip()
        
        if not api_key:
            messagebox.showerror("Error", "Please enter your API key")
            return
            
        if not output_dir:
            messagebox.showerror("Error", "Please select an output directory")
            return
        
        # Run export in separate thread to prevent GUI freezing
        def export_thread():
            try:
                # pass the GUI's queue so build_survey_responses_html emits to the console
                build_survey_responses_html(api_key, pathlib.Path(output_dir), out_queue=self.output_queue)
                self.root.after(0, lambda: messagebox.showinfo(
                    "Success", 
                    "Survey exported successfully!\n"
                    f"Check {output_dir} for the results."))
            except Exception as e:
                raise
                self.root.after(0, lambda: messagebox.showerror(
                    "Error", f"Failed to export survey:\n{str(e)}"))

        threading.Thread(target=export_thread, daemon=True).start()


def main():
    root = tk.Tk()
    app = SurveyExporterGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()