from PIL import Image
import os
import subprocess # Added for iconutil
import shutil # Added for removing the iconset directory
import platform # Added to check OS

def convert_png_to_ico(png_path: str, ico_path: str, sizes: list[tuple[int, int]] | None = None) -> None:
    """Converts a PNG image to an ICO file with specified sizes.

    Args:
        png_path: Path to the input PNG file.
        ico_path: Path to the output ICO file.
        sizes: A list of tuples, where each tuple is (width, height).
               Defaults to standard icon sizes if None.
    """
    if sizes is None:
        sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

    try:
        # Ensure the input file path exists
        if not os.path.exists(png_path):
            print(f"Error: Input PNG file not found at '{png_path}' for ICO conversion.")
            return

        img = Image.open(png_path)

        # Ensure the output directory exists
        output_dir = os.path.dirname(ico_path)
        if output_dir: # Check if output_dir is not empty (i.e., not the current dir)
             os.makedirs(output_dir, exist_ok=True)

        img.save(ico_path, format='ICO', sizes=sizes)
        print(f"Successfully converted '{png_path}' to '{ico_path}' with sizes: {sizes}")

    except FileNotFoundError:
        print(f"Error: Input PNG file not found at '{png_path}' for ICO conversion.")
    except Exception as e:
        print(f"An error occurred during ICO conversion: {e}")

def convert_png_to_icns(png_path: str, icns_path: str) -> None:
    """Converts a PNG image to an ICNS file using iconutil (macOS only).

    Args:
        png_path: Path to the input PNG file (preferably 1024x1024 or larger).
        icns_path: Path to the output ICNS file.
    """
    if platform.system() != "Darwin":
        print("ICNS conversion is only supported on macOS.")
        return

    if not os.path.exists(png_path):
        print(f"Error: Input PNG file not found at '{png_path}' for ICNS conversion.")
        return

    iconset_name = os.path.splitext(os.path.basename(icns_path))[0] + ".iconset"
    iconset_path = os.path.join(os.path.dirname(icns_path), iconset_name)

    try:
        os.makedirs(iconset_path, exist_ok=True)
        img = Image.open(png_path)

        # Define standard ICNS sizes and their corresponding filenames
        # (size, scale_factor for filename, actual_pixel_dimension)
        required_sizes_info = [
            (16, 1, 16), (16, 2, 32),
            (32, 1, 32), (32, 2, 64),
            (128, 1, 128), (128, 2, 256),
            (256, 1, 256), (256, 2, 512),
            (512, 1, 512), (512, 2, 1024)
        ]

        for size, scale, pixel_dim in required_sizes_info:
            filename = f"icon_{size}x{size}{'@' + str(scale) + 'x' if scale > 1 else ''}.png"
            filepath = os.path.join(iconset_path, filename)
            resized_img = img.resize((pixel_dim, pixel_dim), Image.LANCZOS)
            resized_img.save(filepath, "PNG")

        print(f"Successfully created iconset at '{iconset_path}'")

        # Use iconutil to create the .icns file
        # Ensure the output directory for ICNS exists
        output_icns_dir = os.path.dirname(icns_path)
        if output_icns_dir:
            os.makedirs(output_icns_dir, exist_ok=True)
            
        cmd = ["iconutil", "-c", "icns", iconset_path, "-o", icns_path]
        process = subprocess.run(cmd, capture_output=True, text=True)

        if process.returncode == 0:
            print(f"Successfully converted '{iconset_path}' to '{icns_path}'")
        else:
            print(f"Error converting iconset to ICNS: {process.stderr}")

    except FileNotFoundError:
        print(f"Error: Input PNG file not found at '{png_path}' for ICNS conversion.")
    except Exception as e:
        print(f"An error occurred during ICNS conversion: {e}")
    finally:
        # Clean up the .iconset directory
        if os.path.exists(iconset_path):
            shutil.rmtree(iconset_path)
            print(f"Cleaned up temporary iconset directory: '{iconset_path}'")

if __name__ == "__main__":
    # Assuming the script is run from the root of the project (anpe-gui)
    source_png_relative = "anpe_studio/resources/app_icon_logo.png"
    output_ico_relative = "anpe_studio/resources/app_icon_logo.ico"
    output_icns_relative = "anpe_studio/resources/app_icon_mac.icns" # Added ICNS output

    # Get the absolute path to the script's directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Determine workspace root. If script is in project root, script_dir is workspace_root.
    # If script is in a subdirectory, adjust workspace_root accordingly.
    # For this example, let's assume the script convert_icon.py is in the project root.
    workspace_root = script_dir 
    # If your script is, for example, in a 'scripts' subdirectory:
    # workspace_root = os.path.dirname(script_dir) 

    # Construct absolute paths
    abs_source_png = os.path.join(workspace_root, source_png_relative)
    abs_output_ico = os.path.join(workspace_root, output_ico_relative)
    abs_output_icns = os.path.join(workspace_root, output_icns_relative) # Added ICNS output

    # Check if the PNG file actually exists before attempting conversion
    if os.path.exists(abs_source_png):
        convert_png_to_ico(abs_source_png, abs_output_ico)
        if platform.system() == "Darwin": # Only attempt ICNS on macOS
            convert_png_to_icns(abs_source_png, abs_output_icns)
        else:
            print("Skipping ICNS generation as not on macOS.")
    else:
        print(f"Error: Source PNG file not found at the primary expected absolute location: {abs_source_png}")
        print(f"Script directory: {script_dir}")
        print(f"Workspace root used: {workspace_root}")
        print("Please ensure the PNG file exists and the path calculations in the script are correct for your project structure.")
        # Fallback for running script from unexpected CWD is removed for clarity, focus on absolute paths.