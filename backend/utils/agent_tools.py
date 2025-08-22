import os
import glob
import platform
import psutil
import subprocess
import sys
from io import StringIO
import tempfile
import shutil



class AgentTools:
    @staticmethod
    def search_files(directory, pattern):
        """Search for files matching pattern"""
        import glob
        try:
            matches = glob.glob(os.path.join(directory, pattern))
            if matches:
                file_list = "\n".join([f"• {os.path.basename(match)}" for match in matches])
                return f"Found {len(matches)} files:\n{file_list}"
            else:
                return "No files found matching the pattern"
        except Exception as e:
            return f"Error searching files: {str(e)}"
    
    @staticmethod
    def read_file(filepath):
        """Read file contents safely"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except:
            return "Error reading file"
    
    @staticmethod
    def calculate(expression):
        """Safe mathematical calculations"""
        try:
            # Only allow safe operations
            allowed = "0123456789+-*/.() "
            if all(c in allowed for c in expression):
                return str(eval(expression))
            return "Invalid expression"
        except:
            return "Calculation error"
        
    @staticmethod  # <-- Add this line and everything below
    def search_files_in_path(directory, pattern="*.*"):
        """Search for files in a specific directory path"""
        import glob
        import os
        try:
            if not os.path.exists(directory):
                return f"Directory '{directory}' does not exist"
            
            search_path = os.path.join(directory, pattern)
            matches = glob.glob(search_path)
            
            if matches:
                limited_matches = matches[:20]
                file_list = "\n".join([f"• {match}" for match in limited_matches])
                return f"Found {len(matches)} files:\n{file_list}"
            else:
                return f"No files found in '{directory}'"
                
        except Exception as e:
            return f"Error: {str(e)}"
        
    @staticmethod
    def discover_system_info():
        """Dynamically discover what the system can do"""
        import platform
        import psutil
        import subprocess

        capabilities = {
            "system": platform.system(),
            "python_version": platform.python_version(),
            "available_drives": [f"{d}:\\" for d in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if os.path.exists(f"{d}:\\")],
            "memory_gb": round(psutil.virtual_memory().total / (1024**3), 1),
            "cpu_cores": psutil.cpu_count(),
            "gpu_info": subprocess.check_output("wmic path win32_VideoController get name", shell=True, text=True).strip().split('\n')[1:] if platform.system() == "Windows" else "GPU detection not available on this OS",
            "installed_modules": []
        }

        modules_to_check = ['requests', 'pandas', 'numpy', 'opencv-cv2', 'pillow', 'matplotlib', 'selenium', 'beautifulsoup4']
        for module in modules_to_check:
            try:
                __import__(module)
                capabilities["installed_modules"].append(module)
            except ImportError:
                pass

        return capabilities
    
    @staticmethod
    def execute_python_code(code):
        """Execute Python code safely and return output"""
        import sys
        from io import StringIO
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        captured_output = StringIO()
        captured_error = StringIO()
        try:
            
            sys.stdout = captured_output
            sys.stderr = captured_error

            exec(code)

            output = captured_output.getvalue()
            error = captured_error.getvalue()


            if error:
                return f"Error: {error}"
            return output if output else "Code executed successfully (no output)"
        except Exception as e:
            return f"Execution Error: {str(e)}"
        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr

    @staticmethod
    def execute_csharp_code(code):
            """Execute C# code using dotnet"""
            import subprocess
            import tempfile
            import os
            import shutil
            try:
                    temp_dir = os.path.join(tempfile.gettempdir(), f"csharp_temp_{os.getpid()}")
                    os.makedirs(temp_dir, exist_ok=True)

                    try:
                        subprocess.run(['dotnet', 'new', 'console', '--force'], 
                                      cwd=temp_dir, capture_output=True, text=True, check=True)
                        
                        program_file = os.path.join(temp_dir, 'Program.cs')
                                            
                        if 'class Program' not in code and 'static void Main' not in code:
                            wrapped_code = f"""using System;


using System;
class Program 
{{
    static void Main() 
    {{
        {code}
    }}
}}"""
                        else:
                          wrapped_code = code

                        with open(program_file, 'w', encoding='utf-8') as f:
                         f.write(wrapped_code)

                        result = subprocess.run(['dotnet', 'run'], 
                                  cwd=temp_dir, capture_output=True, text=True, timeout=10)
                                

                        if result.returncode == 0:
                          return result.stdout.strip() if result.stdout.strip() else "C# executed successfully"
                        else:
                          return f"C# Error: {result.stderr.strip()}"
                        
                    finally:
                        try:
                            shutil.rmtree(temp_dir)
                        except:
                            pass

            except subprocess.TimeoutExpired:
                return "C# execution timeout"
            except Exception as e:
                return f"C# Error: {result.stderr.strip()}"