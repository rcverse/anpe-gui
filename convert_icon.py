from PIL import Image
import os

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
            print(f"Error: Input file not found at '{png_path}'")
            return

        img = Image.open(png_path)

        # Ensure the output directory exists
        output_dir = os.path.dirname(ico_path)
        if output_dir: # Check if output_dir is not empty (i.e., not the current dir)
             os.makedirs(output_dir, exist_ok=True)

        img.save(ico_path, format='ICO', sizes=sizes)
        print(f"Successfully converted '{png_path}' to '{ico_path}' with sizes: {sizes}")

    except FileNotFoundError: # This might be redundant now but kept for safety
        print(f"Error: Input file not found at '{png_path}'")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    # Assuming the script is run from the root of the project (anpe-gui)
    source_png = "anpe_studio/resources/app_icon_logo.png" # Relative path from project root
    output_ico = "anpe_studio/resources/app_icon.ico"    # Relative path from project root

    # Get the absolute path to the script's directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Get the absolute path to the workspace root (assuming script is in the root)
    workspace_root = script_dir # Or adjust if script is elsewhere

    # Construct absolute paths
    abs_source_png = os.path.join(workspace_root, source_png)
    abs_output_ico = os.path.join(workspace_root, output_ico)


    # Check if the PNG file actually exists before attempting conversion
    if os.path.exists(abs_source_png):
        convert_png_to_ico(abs_source_png, abs_output_ico)
    else:
        print(f"Error: Source PNG file not found at the expected location: {abs_source_png}")
        print("Please ensure the file exists and the path in the script is correct.")
        # Attempt relative path as a fallback, in case the script is run from a different CWD
        print(f"Attempting relative path: {source_png}")
        if os.path.exists(source_png):
             convert_png_to_ico(source_png, output_ico)
        else:
             print(f"Error: Source PNG file also not found at relative path: {source_png}")