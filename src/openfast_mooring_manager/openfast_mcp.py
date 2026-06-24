import os
import glob
import subprocess
from urllib.request import urlopen
from fastmcp import FastMCP
from openfast_toolbox.io import FASTInputFile

# Create the MCP Server instance
mcp = FastMCP(
    "OpenFAST Mooring Manager"
)

# Base URL for the raw files from that exact commit
RAW_GITHUB_BASE = "https://raw.githubusercontent.com/IEAWindSystems/IEA-15-240-RWT/86d51c8a1ee65be4f3686087a5c443c0b57e5cfb/OpenFAST/IEA-15-240-RWT-UMaineSemi"

# Registry mapping user-friendly names or modules to their precise remote filenames
IEA_15MW_FILES = {
    "master": "IEA-15-240-RWT-UMaineSemi.fst",
    "moordyn": "IEA-15-240-RWT-UMaineSemi_MoorDyn.dat",
    "hydrodyn": "IEA-15-240-RWT-UMaineSemi_HydroDyn.dat",
    "elastodyn": "IEA-15-240-RWT-UMaineSemi_ElastoDyn.dat",
    "aerodyn": "IEA-15-240-RWT-UMaineSemi_AeroDyn15.dat",
    "servodyn": "IEA-15-240-RWT-UMaineSemi_ServoDyn.dat"
}

@mcp.resource("openfast://templates/iea15mw/{file_key}")
def get_iea15mw_remote_template(file_key: str) -> str:
    """
    Dynamically fetches the official reference files for the IEA 15MW 
    floating turbine directly from the specified GitHub commit.
    
    Args:
        file_key (str): The component key (e.g., 'master', 'moordyn', 'hydrodyn')
    """
    key = file_key.lower()
    if key not in IEA_15MW_FILES:
        return f"Error: Unknown file key '{file_key}'. Available keys: {list(IEA_15MW_FILES.keys())}"
    
    filename = IEA_15MW_FILES[key]
    remote_url = f"{RAW_GITHUB_BASE}/{filename}"
    
    try:
        # Fetching the raw text file from GitHub
        with urlopen(remote_url, timeout=10) as response:
            content = response.read().decode('utf-8')
        return f"=== Remote Reference Template: {filename} ===\nURL: {remote_url}\n\n{content}"
    except Exception as e:
        return f"Failed to stream template from GitHub: {str(e)}\nAttempted URL: {remote_url}"


@mcp.resource("openfast://templates/complete-models")
def list_complete_models() -> str:
    """Exposes the remote model details to the LLM context."""
    summary = [
        "=== CATALOGUE DES MODÈLES COMPLETS OPENFAST DISPONIBLES ===",
        "\n🏷️ Identifiant : iea15mw",
        "  Modèle : IEA 15MW Floating Offshore Wind Turbine (UMaine VolturnUS-S)",
        "  Source : GitHub (IEAWindSystems Repository - Fixed Commit)",
        "  Spécificités : Modèle officiel de 15MW en eau profonde (200m) couplé à MoorDyn.",
        "  Fichiers disponibles via openfast://templates/iea15mw/{key} :"
    ]
    for key, filename in IEA_15MW_FILES.items():
        summary.append(f"    - Key: '{key}' maps to {filename}")
        
    return "\n".join(summary)

@mcp.tool()
def load_openfast_model(fst_path: str) -> str:
    """
    Loads a master OpenFAST configuration file (.fst), returns summary flags, 
    and detects paths to associated files (like MoorDyn or HydroDyn files).
    
    Args:
        fst_path (str): Absolute or relative path to the main .fst file.
    """
    if not os.path.exists(fst_path):
        return f"Error: Main model file '{fst_path}' does not exist."
    
    try:
        # Load the configuration using openfast_toolbox
        fst = FASTInputFile(fst_path)
        
        # Extract critical orchestration flags
        comp_mooring = fst.get('CompMooring', 'N/A')
        mooring_file = fst.get('MooringFile', 'N/A')
        hydro_file = fst.get('HydroFile', 'N/A')
        
        summary = [
            "=== OpenFAST Master Model Loaded ===",
            f"Primary File: {os.path.basename(fst_path)}",
            f"CompMooring Flag: {comp_mooring} (0: None, 1: MAP++, 2: FEAMooring, 3: MoorDyn, 4: OrcaFlex)",
            f"Mooring Structural File Path: {mooring_file}",
            f"Hydrodynamics File Path: {hydro_file}\n",
            "--- Master Configuration Keys Available ---"
        ]
        
        for k, v in fst.items():
            summary.append(f"  {k}: {v}")
            
        return "\n".join(summary)
        
    except Exception as e:
        return f"Failed to load .fst model: {str(e)}"


@mcp.tool()
def read_mooring_file(file_path: str) -> str:
    """
    Reads and outputs the text contents of an isolated mooring layout file (e.g., MoorDyn .dat).
    This allows the LLM to understand lines, connection nodes, and material types.
    
    Args:
        file_path (str): Path to the target mooring data file.
    """
    if not os.path.exists(file_path):
        return f"Error: Mooring file path '{file_path}' not found."
        
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        return f"=== Mooring Layout File ({file_path}) ===\n{content}"
    except Exception as e:
        return f"Failed to read mooring configuration: {str(e)}"


@mcp.tool()
def update_mooring_line_property(file_path: str, line_id: int, property_name: str, new_value: str) -> str:
    """
    Updates a specific attribute (e.g., UnstrLen, LineType, NumSegs) of a given Mooring Line ID 
    inside a tabular MoorDyn data file.
    
    Args:
        file_path (str): Path to the MoorDyn configuration data file.
        line_id (int): The structural Line ID number to modify.
        property_name (str): The column variable to adjust (e.g., 'UnstrLen').
        new_value (str): The new value assignment (e.g., '850.5').
    """
    if not os.path.exists(file_path):
        return f"Error: File target '{file_path}' not found."
        
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
            
        in_lines_section = False
        headers = []
        modified = False
        
        for i, line in enumerate(lines):
            # Track relevant file subsections
            if "LINE PROPERTIES" in line.upper() or "LINE TYPES" in line.upper():
                in_lines_section = False
                continue
            if "LINES" in line.upper() and "PROPERTIES" not in line.upper():
                in_lines_section = True
                continue
                
            if in_lines_section:
                # Capture table headers dynamically if available
                if line.strip().startswith(('ID', '(')):
                    if not line.strip().startswith('('):
                        headers = [h.strip() for h in line.split() if h.strip()]
                    continue
                if line.strip().startswith('-') or not line.strip():
                    continue
                    
                parts = line.split()
                if parts and parts[0].isdigit() and int(parts[0]) == line_id:
                    # Fallback to defaults if custom header string manipulation missed
                    if not headers:
                        headers = ['ID', 'LineType', 'AttachA', 'AttachB', 'UnstrLen', 'NumSegs', 'Outputs']
                    
                    try:
                        col_idx = [h.upper() for h in headers].index(property_name.upper())
                        parts[col_idx] = str(new_value)
                        
                        # Rebuild row line with spacing preservation
                        lines[i] = "    " + "    ".join(parts) + "\n"
                        modified = True
                        break
                    except ValueError:
                        return f"Error: Column parameter '{property_name}' not discovered in table headers: {headers}"
                        
        if modified:
            with open(file_path, 'w') as f:
                f.writelines(lines)
            return f"Success: Mooring Line {line_id} updated via '{property_name}' to '{new_value}' in {file_path}."
        return f"Error: Line ID {line_id} was not identified in the LINES block."
            
    except Exception as e:
        return f"Error during parsing and adjustment processing: {str(e)}"


@mcp.tool()
def modify_general_config_param(file_path: str, key: str, value: str) -> str:
    """
    Modifies a standard Key-Value pair scalar parameter in any compatible OpenFAST text setup file.
    
    Args:
        file_path (str): Target configuration file path.
        key (str): Parameter key string (e.g., 'TMax', 'DT').
        value (str): The configuration adjustment payload string.
    """
    if not os.path.exists(file_path):
        return f"Error: File target '{file_path}' not found."
    try:
        f = FASTInputFile(file_path)
        
        # Simple type conversion helper
        if value.lower() == 'true':
            typed_val = True
        elif value.lower() == 'false':
            typed_val = False
        else:
            try:
                typed_val = float(value) if '.' in value else int(value)
            except ValueError:
                typed_val = value
                
        f[key] = typed_val
        f.write(file_path)
        return f"Success: Parameter '{key}' committed to value '{value}' inside {file_path}."
    except Exception as e:
        return f"Openfast_toolbox write pipeline failed: {str(e)}"


@mcp.tool()
def run_openfast_simulation(fst_path: str) -> str:
    """
    Executes an OpenFAST simulation using Docker. The tool automatically maps 
    the file directory to the container's '/files' mount volume.
    
    Args:
        fst_path (str): Absolute or relative path to the main .fst file on the host.
    """
    if not os.path.exists(fst_path):
        return f"Error: OpenFAST file '{fst_path}' not found on host."
    
    # Resolve the absolute pathing to handle volume mounts correctly
    abs_fst_path = os.path.abspath(fst_path)
    host_dir = os.path.dirname(abs_fst_path)
    fst_filename = os.path.basename(abs_fst_path)
    
    # Construct command targeting the fixed internal container directory: /files
    command = [
        "docker", "run", "--rm",
        f"--volume={host_dir}:/files",
        "nrel/openfast:latest",
        "openfast", f"/files/{fst_filename}"
    ]
    
    try:
        # Run the container and grab execution pipeline feedback
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return f"=== OpenFAST Simulation Completed Successfully ===\n\n[STDOUT]\n{result.stdout}"
    except subprocess.CalledProcessError as e:
        return (
            f"Error: OpenFAST execution exited with non-zero status code {e.returncode}.\n\n"
            f"[STDOUT]\n{e.stdout}\n"
            f"[STDERR]\n{e.stderr}"
        )
    except Exception as e:
        return f"An unexpected error occurred while spinning up Docker: {str(e)}"


# Define a Prompt template to initialize conversation design cleanly
@mcp.prompt()
def manage_mooring_workflow(fst_file_path: str = "") -> str:
    """
    Sets up an engineering interaction context guiding the agent on model interrogation.
    """
    return f"""You are an offshore engineering assistant specialized in aero-hydro-elastic modeling via OpenFAST.
Your workflow is to collaborate with the user to inspect their model configuration, modify mooring line traits, and execute simulations.

Current Context:
Target Model File: {fst_file_path if fst_file_path else "Not provided yet"}

Instructions:
1. If the target model .fst file is not specified, politely request the workspace path from the user.
2. Call `load_openfast_model` to verify global properties, tracking `CompMooring` and pathing to sub-configuration components.
3. Expose layout structures to the user using `read_mooring_file`.
4. Suggest optimization options, line replacements, or specific segment modifications based on their criteria.
5. Apply modifications accurately using `update_mooring_line_property` or `modify_general_config_param`.
6. Once configuration tasks are locked in, offer to run the simulation via `run_openfast_simulation`.
"""

if __name__ == "__main__":
    mcp.run()