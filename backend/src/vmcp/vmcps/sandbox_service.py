"""
Sandbox Service for vMCP

Manages per-vMCP sandbox environments with isolated Python virtual environments.
Each sandbox is stored at ~/.vmcp/{vmcp_id}/ with its own uv virtual environment.

Architecture:
- Uses uv (host) to create and manage virtual environments
- Each sandbox has a pyproject.toml file for package management
- vmcp package is installed from TestPyPI (includes vmcp-sdk, vmcp-sdk-cli, vmcp)
- Default packages are installed from PyPI
- pip is available in venv so 'pip install' commands work within the sandbox

Host vs Venv Operations:
- uv command: Always uses host uv (found via PATH or ~/.local/bin/uv)
- venv creation: Uses host uv to create venv
- package installation: Uses host uv to install packages into venv
- pip commands: When executed in sandbox, use venv pip (installed via ensurepip)
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from vmcp.utilities.logging import get_logger

logger = get_logger(__name__)

class SandboxService:
    """Service for managing per-vMCP sandbox environments."""
    
    SANDBOX_BASE = Path.home() / ".vmcp"

    @property
    def _config_dir(self) -> Path:
        return Path(__file__).parent / "sandbox_config"

    def _load_prompt(self, filename: str) -> str:
        prompt_path = self._config_dir / filename
        try:
            if not prompt_path.exists():
                logger.error(f"Prompt file not found at {prompt_path}")
                return ""
            return prompt_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to load prompt from {prompt_path}: {e}")
            return ""

    # Setup prompt for progressive discovery mode only (PD enabled, sandbox disabled)
    @property
    def SETUP_PROMPT_PD_ONLY(self) -> str:
        return self._load_prompt("prompt_pd_only.md")

    # Setup prompt for progressive discovery mode with sandbox (PD enabled, sandbox enabled)
    @property
    def SETUP_PROMPT_PROGRESSIVE_DISCOVERY(self) -> str:
        return self._load_prompt("prompt_progressive_discovery.md")

    # Setup prompt for SDK-only mode (sandbox enabled, PD disabled)
    @property
    def SETUP_PROMPT_SDK_ONLY(self) -> str:
        return self._load_prompt("prompt_sdk_only.md")

    
    def __init__(self):
        """Initialize the sandbox service."""
        self.SANDBOX_BASE.mkdir(parents=True, exist_ok=True)
    
    def get_sandbox_path(self, vmcp_id: str) -> Path:
        """
        Get the sandbox directory path for a vMCP.
        
        Args:
            vmcp_id: The vMCP ID
            
        Returns:
            Path to the sandbox directory
        """
        # Sanitize vmcp_id for filesystem safety
        safe_id = self._sanitize_vmcp_id(vmcp_id)
        return self.SANDBOX_BASE / safe_id
    
    def _sanitize_vmcp_id(self, vmcp_id: str) -> str:
        """
        Sanitize vmcp_id for use in filesystem paths.
        
        Args:
            vmcp_id: The vMCP ID
            
        Returns:
            Sanitized ID safe for filesystem
        """
        # Remove or replace unsafe characters
        safe = vmcp_id.replace("/", "_").replace("\\", "_")
        safe = safe.replace("..", "_").replace("~", "_")
        # Remove any remaining problematic characters
        safe = "".join(c for c in safe if c.isalnum() or c in "._-")
        return safe or "default"
    
    def sandbox_exists(self, vmcp_id: str) -> bool:
        """
        Check if sandbox directory exists.
        
        Args:
            vmcp_id: The vMCP ID
            
        Returns:
            True if sandbox directory exists
        """
        sandbox_path = self.get_sandbox_path(vmcp_id)
        return sandbox_path.exists() and sandbox_path.is_dir()
    
    def venv_exists(self, vmcp_id: str) -> bool:
        """
        Check if virtual environment exists in sandbox.
        
        Args:
            vmcp_id: The vMCP ID
            
        Returns:
            True if venv exists
        """
        sandbox_path = self.get_sandbox_path(vmcp_id)
        venv_path = sandbox_path / ".venv"
        return venv_path.exists() and venv_path.is_dir()
    
    def is_enabled(self, vmcp_id: str, vmcp_config: Optional[Any] = None) -> bool:
        """
        Check if sandbox is enabled.
        
        Only checks the metadata flag (sandbox_enabled in vMCP metadata).
        Does not check filesystem state.
        
        Args:
            vmcp_id: The vMCP ID
            vmcp_config: Optional VMCPConfig object to check metadata (avoids extra DB call)
            
        Returns:
            True if sandbox_enabled flag is True in metadata, False otherwise
        """
        # Check metadata if config provided
        if vmcp_config is not None:
            metadata = getattr(vmcp_config, 'metadata', {}) or {}
            if isinstance(metadata, dict):
                sandbox_enabled = metadata.get('sandbox_enabled')
                return sandbox_enabled is True
        
        # If no config provided, default to False
        return False
    
    def _find_uv_command(self) -> str:
        """
        Find the uv command to use.
        
        Returns:
            Path to uv command
            
        Raises:
            RuntimeError: If uv is not found
        """
        # Check system PATH
        if shutil.which("uv"):
            return "uv"
        # Check ~/.local/bin/uv
        local_uv = Path.home() / ".local" / "bin" / "uv"
        if local_uv.exists():
            return str(local_uv)
        raise RuntimeError(
            "uv is required but not found. Please install uv: "
            "curl -LsSf https://astral.sh/uv/install.sh | sh"
        )
    
    def _get_venv_python(self, venv_path: Path) -> Path:
        """
        Get the Python executable path in the virtual environment.
        
        Args:
            venv_path: Path to the venv directory
            
        Returns:
            Path to Python executable
            
        Raises:
            RuntimeError: If Python executable not found
        """
        # Try Unix path first
        venv_python = venv_path / "bin" / "python"
        if venv_python.exists():
            return venv_python
        
        # Try Windows path
        venv_python = venv_path / "Scripts" / "python.exe"
        if venv_python.exists():
            return venv_python
        
        raise RuntimeError(f"Python executable not found in venv: {venv_path}")
    
    def _create_pyproject_toml(self, sandbox_path: Path) -> None:
        """
        Create pyproject.toml file in sandbox directory.
        
        Args:
            sandbox_path: Path to sandbox directory
        """
        template_path = self._config_dir / "pyproject.toml.template"
        target_path = sandbox_path / "pyproject.toml"
        
        if template_path.exists():
            template_content = template_path.read_text(encoding="utf-8")
            target_path.write_text(template_content, encoding="utf-8")
            logger.info(f"Created pyproject.toml in sandbox: {target_path}")
        else:
            logger.warning(f"pyproject.toml template not found at {template_path}, creating minimal version")
            # Create minimal pyproject.toml
            minimal_content = """[project]
name = "vmcp-sandbox"
version = "0.1.0"
description = "vMCP Sandbox Environment"
requires-python = ">=3.10,<3.14"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
"""
            target_path.write_text(minimal_content, encoding="utf-8")
            logger.info(f"Created minimal pyproject.toml in sandbox: {target_path}")
    
    def _create_requirements_txt(self, sandbox_path: Path) -> None:
        """
        Create requirements.txt file in sandbox directory.
        
        Args:
            sandbox_path: Path to sandbox directory
        """
        template_path = self._config_dir / "requirements.txt.template"
        target_path = sandbox_path / "requirements.txt"
        
        if template_path.exists():
            template_content = template_path.read_text(encoding="utf-8")
            target_path.write_text(template_content, encoding="utf-8")
            logger.info(f"Created requirements.txt in sandbox: {target_path}")
        else:
            logger.warning(f"requirements.txt template not found at {template_path}")
    
    def _create_sandbox_config(self, sandbox_path: Path, vmcp_id: str) -> None:
        """
        Create sandbox config file with vmcp_id.
        
        Args:
            sandbox_path: Path to sandbox directory
            vmcp_id: The vMCP ID to store
        """
        import json
        config_path = sandbox_path / ".vmcp-config.json"
        config_data = {
            "vmcp_id": vmcp_id
        }
        with open(config_path, 'w') as f:
            json.dump(config_data, f, indent=2)
        logger.info(f"Created sandbox config file: {config_path}")
    
    def _preload_list_tools_script(self, sandbox_path: Path) -> None:
        """
        Preload list_tools.py script into the sandbox directory.
        
        Args:
            sandbox_path: Path to sandbox directory
        """
        try:
            # Get the path to list_tools.py in the source directory
            current_file = Path(__file__).resolve()
            source_script = current_file.parent / "list_tools.py"
            
            if not source_script.exists():
                logger.warning(f"list_tools.py not found at {source_script}, skipping preload")
                return
            
            # Copy to sandbox directory
            target_script = sandbox_path / "list_tools.py"
            if not target_script.exists():
                import shutil
                shutil.copy2(source_script, target_script)
                # Make it executable
                target_script.chmod(0o755)
                logger.info(f"Preloaded list_tools.py to {target_script}")
            else:
                logger.debug("list_tools.py already exists in sandbox, skipping")
        except Exception as e:
            logger.warning(f"Failed to preload list_tools.py: {e}")
    
    def get_sandbox_vmcp_id(self, sandbox_path: Optional[Path] = None) -> Optional[str]:
        """
        Get vmcp_id from sandbox config file.
        
        Args:
            sandbox_path: Path to sandbox directory. If None, tries to detect from current directory.
            
        Returns:
            vmcp_id if found, None otherwise
        """
        import json
        
        if sandbox_path is None:
            # Try to detect from current working directory
            cwd = Path.cwd()
            # Check if we're in a sandbox directory (~/.vmcp/{vmcp_id})
            if str(cwd).startswith(str(self.SANDBOX_BASE)):
                sandbox_path = cwd
            else:
                return None

        config_path = sandbox_path / ".vmcp-config.json"
        if not config_path.exists():
            return None

        try:
            with open(config_path, 'r') as f:
                config_data = json.load(f)
                return config_data.get("vmcp_id")
        except (json.JSONDecodeError, KeyError, IOError) as e:
            logger.warning(f"Error reading sandbox config: {e}")
            return None
    

    def _ensure_pip_in_venv(self, venv_python: Path) -> bool:
        """
        Ensure pip is installed in the virtual environment.
        This allows 'pip install' commands to work within the venv.
        
        Args:
            venv_python: Path to the Python executable in the venv
            
        Returns:
            True if pip is available, False otherwise
        """
        try:
            # Check if pip is already available
            result = subprocess.run(
                [str(venv_python), "-m", "pip", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                logger.debug("pip is already available in venv")
                return True
            
            # If pip is not available, install it using ensurepip
            logger.info("Installing pip in virtual environment (venv)")
            result = subprocess.run(
                [str(venv_python), "-m", "ensurepip", "--upgrade"],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to install pip in venv: {result.stderr}")
                return False
            
            logger.info("Successfully installed pip in virtual environment (venv)")
            return True
            
        except subprocess.TimeoutExpired:
            logger.error("Timeout installing pip in venv")
            return False
        except Exception as e:
            logger.error(f"Error ensuring pip is installed in venv: {e}", exc_info=True)
            return False

    def _sync_packages_from_requirements(self, sandbox_path: Path, uv_cmd: str, venv_python: Path) -> bool:
        """
        Install packages from requirements.txt using uv pip install.
        
        Args:
            sandbox_path: Path to sandbox directory containing requirements.txt
            uv_cmd: uv command path (from host)
            venv_python: Path to Python executable in venv
            
        Returns:
            True if successful, False otherwise
        """
        try:
            requirements_path = sandbox_path / "requirements.txt"
            if not requirements_path.exists():
                logger.warning(f"requirements.txt not found at {requirements_path}, skipping package installation")
                return True  # Not an error if requirements.txt doesn't exist
            
            logger.info("Installing packages from requirements.txt using uv pip install")
            
            # Install from requirements.txt
            result = subprocess.run(
                [
                    uv_cmd, "pip", "install",
                    "--python", str(venv_python),
                    "-r", str(requirements_path)
                ],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to install packages from requirements.txt: {result.stderr}")
                return False
            
            logger.info("Successfully installed packages from requirements.txt")
            return True
            
        except subprocess.TimeoutExpired:
            logger.error("Timeout installing packages from requirements.txt")
            return False
        except Exception as e:
            logger.error(f"Error installing packages from requirements.txt: {e}", exc_info=True)
            return False
    
    def _install_vmcp_from_testpypi(self, venv_python: Path, uv_cmd: str) -> bool:
        """
        Install 1xn-vmcp package from TestPyPI into the virtual environment.
        This installs the latest version of 1xn-vmcp (which includes vmcp, vmcp_sdk, and vmcp-sdk-cli).
        
        Args:
            venv_python: Path to the Python executable in the venv
            uv_cmd: uv command path (from host)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("Installing latest 1xn-vmcp package from TestPyPI into venv")
            
            # Use uv (host) to install from TestPyPI into venv
            # Use --index-url for TestPyPI (primary) and --extra-index-url for PyPI (for dependencies)
            # --index-strategy unsafe-best-match allows checking all indexes to find the latest version
            # --no-cache ensures we get the latest version from TestPyPI, not a cached one
            # --upgrade ensures we upgrade to the latest version if already installed
            # This ensures 1xn-vmcp comes from TestPyPI (where it exists), while dependencies come from PyPI
            # uv pip install --no-cache --upgrade --index-strategy unsafe-best-match --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ --python <venv_python> 1xn-vmcp
            result = subprocess.run(
                [
                    uv_cmd, "pip", "install",
                    "--no-cache",
                    "--upgrade",
                    "--index-strategy", "unsafe-best-match",
                    "--index-url", "https://test.pypi.org/simple/",
                    "--extra-index-url", "https://pypi.org/simple/",
                    "--python", str(venv_python),
                    "1xn-vmcp"
                ],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to install 1xn-vmcp from TestPyPI: {result.stderr}")
                return False
            
            logger.info("Successfully installed latest 1xn-vmcp package from TestPyPI into venv")
            return True
            
        except subprocess.TimeoutExpired:
            logger.error("Timeout installing 1xn-vmcp from TestPyPI")
            return False
        except Exception as e:
            logger.error(f"Error installing 1xn-vmcp from TestPyPI: {e}", exc_info=True)
            return False
    
    def create_sandbox(self, vmcp_id: str) -> bool:
        """
        Create sandbox directory and uv virtual environment.
        
        Process:
        1. Create sandbox directory
        2. Create pyproject.toml template
        3. Create virtual environment using uv (host)
        4. Ensure pip is available in venv
        5. Install 1xn-vmcp package from TestPyPI into venv
        6. Run uv sync to install dependencies from pyproject.toml
        7. Create sandbox config and preload scripts
        
        Args:
            vmcp_id: The vMCP ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Find uv command (required, will raise if not found)
            uv_cmd = self._find_uv_command()
            
            # Create sandbox directory
            sandbox_path = self.get_sandbox_path(vmcp_id)
            sandbox_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created sandbox directory: {sandbox_path}")
            
            # Create requirements.txt template (pyproject.toml not needed anymore)
            self._create_requirements_txt(sandbox_path)
            
            # Create virtual environment using uv (host)
            venv_path = sandbox_path / ".venv"
            logger.info(f"Creating virtual environment using uv (host): {uv_cmd}")
            result = subprocess.run(
                [uv_cmd, "venv", str(venv_path)],
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode != 0:
                logger.error(f"Failed to create venv with uv: {result.stderr}")
                return False
            logger.info(f"Created virtual environment: {venv_path}")
            
            # Get Python executable in venv
            venv_python = self._get_venv_python(venv_path)
            
            # Ensure pip is installed in venv (so 'pip install' commands work in venv)
            if not self._ensure_pip_in_venv(venv_python):
                logger.error("Failed to ensure pip is installed in venv")
                return False
            
            # Install 1xn-vmcp package from TestPyPI into venv
            # This installs 1xn-vmcp (which includes vmcp, vmcp_sdk, and vmcp-sdk-cli)
            if not self._install_vmcp_from_testpypi(venv_python, uv_cmd):
                logger.error("Failed to install 1xn-vmcp from TestPyPI")
                return False
            
            # Install packages from requirements.txt
            if not self._sync_packages_from_requirements(sandbox_path, uv_cmd, venv_python):
                logger.warning("Failed to install packages from requirements.txt, but continuing...")
            
            # Create sandbox config file with vmcp_id
            self._create_sandbox_config(sandbox_path, vmcp_id)
            
            logger.info(f"✅ Sandbox created successfully: {sandbox_path}")
            return True
            
        except RuntimeError as e:
            logger.error(f"Configuration error: {e}")
            return False
        except subprocess.TimeoutExpired:
            logger.error("Timeout creating sandbox")
            return False
        except Exception as e:
            logger.error(f"Error creating sandbox: {e}", exc_info=True)
            return False
    
    def _setup_venv_and_packages(self, sandbox_path: Path, vmcp_id: str) -> bool:
        """
        Setup virtual environment and install packages in an existing sandbox directory.
        This is used when sandbox directory exists but venv needs to be created.
        
        Args:
            sandbox_path: Path to existing sandbox directory
            vmcp_id: The vMCP ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Find uv command (required, will raise if not found)
            uv_cmd = self._find_uv_command()
            
            # Create requirements.txt if it doesn't exist (pyproject.toml not needed)
            requirements_path = sandbox_path / "requirements.txt"
            if not requirements_path.exists():
                self._create_requirements_txt(sandbox_path)
            
            # Create virtual environment using uv (host)
            venv_path = sandbox_path / ".venv"
            logger.info(f"Creating virtual environment using uv (host): {uv_cmd}")
            result = subprocess.run(
                [uv_cmd, "venv", str(venv_path)],
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode != 0:
                logger.error(f"Failed to create venv with uv: {result.stderr}")
                return False
            logger.info(f"Created virtual environment: {venv_path}")
            
            # Get Python executable in venv
            venv_python = self._get_venv_python(venv_path)
            
            # Ensure pip is installed in venv
            if not self._ensure_pip_in_venv(venv_python):
                logger.error("Failed to ensure pip is installed in venv")
                return False
            
            # Install vmcp package from TestPyPI into venv
            if not self._install_vmcp_from_testpypi(venv_python, uv_cmd):
                logger.error("Failed to install vmcp from TestPyPI")
                return False
            
            # Install packages from requirements.txt
            if not self._sync_packages_from_requirements(sandbox_path, uv_cmd, venv_python):
                logger.warning("Failed to install packages from requirements.txt, but continuing...")
            
            # Ensure config file exists
            config_path = sandbox_path / ".vmcp-config.json"
            if not config_path.exists():
                self._create_sandbox_config(sandbox_path, vmcp_id)
            
            logger.info(f"✅ Virtual environment setup successfully in: {sandbox_path}")
            return True
            
        except RuntimeError as e:
            logger.error(f"Configuration error: {e}")
            return False
        except subprocess.TimeoutExpired:
            logger.error("Timeout setting up venv")
            return False
        except Exception as e:
            logger.error(f"Error setting up venv: {e}", exc_info=True)
            return False
    
    
    def delete_sandbox(self, vmcp_id: str) -> bool:
        """
        Delete the sandbox directory and all its contents.
        
        Args:
            vmcp_id: The vMCP ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            sandbox_path = self.get_sandbox_path(vmcp_id)
            if not sandbox_path.exists():
                logger.info(f"Sandbox directory does not exist: {sandbox_path}")
                return True  # Consider it successful if it doesn't exist
            
            logger.info(f"Deleting sandbox directory: {sandbox_path}")
            
            # Use shutil.rmtree with error handling for locked files
            # On Windows, files might be locked, so we use onerror handler
            def handle_remove_readonly(func, path, exc):
                """
                Handle permission errors when deleting files.
                On Windows, files might be read-only.
                """
                import stat
                if func in (os.unlink, os.remove) and os.path.exists(path):
                    # Change file permissions to allow deletion
                    os.chmod(path, stat.S_IWRITE)
                    func(path)
                elif func == os.rmdir:
                    # Try to remove directory again
                    try:
                        os.rmdir(path)
                    except OSError:
                        pass
            
            # Delete the directory tree
            shutil.rmtree(sandbox_path, onerror=handle_remove_readonly)
            
            # Verify deletion
            if sandbox_path.exists():
                logger.warning(f"Sandbox directory still exists after deletion attempt: {sandbox_path}")
                # Try one more time with force
                try:
                    import stat
                    # Make all files writable
                    for root, dirs, files in os.walk(sandbox_path):
                        for d in dirs:
                            os.chmod(os.path.join(root, d), stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
                        for f in files:
                            os.chmod(os.path.join(root, f), stat.S_IWRITE | stat.S_IREAD)
                    shutil.rmtree(sandbox_path, onerror=handle_remove_readonly)
                except Exception as e2:
                    logger.error(f"Failed to force delete sandbox directory: {e2}")
                    return False
            
            # Final verification
            if sandbox_path.exists():
                logger.error(f"Failed to delete sandbox directory: {sandbox_path} still exists")
                return False
            
            logger.info(f"Successfully deleted sandbox directory: {sandbox_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting sandbox for {vmcp_id}: {e}", exc_info=True)
            return False
    
    def _get_execute_python_tool(self, sandbox_path_str: str) -> Dict[str, Any]:
        """
        Get execute_python tool definition (not surfaced, but kept for reference).
        
        Args:
            sandbox_path_str: String path to sandbox directory
            
        Returns:
            Tool definition dictionary
        """
        # Load execute_python code from file and inject sandbox path
        execute_python_code = self._load_tool_code("tool_execute_python.py").replace("{sandbox_path_str}", sandbox_path_str)

        return {
            "name": "execute_python",
            "description": "Execute Python code in a sandboxed environment.",
            "text": f"The Python code will be executed in a sandboxed environment. The sandbox directory appears as /root/ to the LLM (e.g., 'os.getcwd()' returns /root). The actual sandbox is located at {sandbox_path_str} with filesystem and network restrictions applied. The sandbox prevents access to sensitive directories and restricts network access.",
            "tool_type": "python",
            "code": execute_python_code,
            "variables": [
                {
                    "name": "code",
                    "description": "The Python code to execute",
                    "required": True,
                    "type": "str"
                },
                {
                    "name": "timeout",
                    "description": "Maximum execution time in seconds",
                    "required": False,
                    "type": "int"
                }
            ],
            "environment_variables": [],
            "tool_calls": []
        }

    
    # helper to load tool code
    def _load_tool_code(self, filename: str) -> str:
        tool_path = self._config_dir / "sandbox_tools" / filename
        try:
            if not tool_path.exists():
                logger.error(f"Tool file not found at {tool_path}")
                return ""
            return tool_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to load tool code from {tool_path}: {e}")
            return ""

    def get_sandbox_tools(self, vmcp_id: str) -> List[Dict[str, Any]]:
        """
        Get sandbox tool definitions to inject into vMCP.
        Includes base tools (execute_bash) and dynamically discovered tools.
        Note: execute_python tool is kept in _get_execute_python_tool() but not surfaced.
        
        Args:
            vmcp_id: The vMCP ID
            
        Returns:
            List of tool definitions
        """
        sandbox_path = self.get_sandbox_path(vmcp_id)
        sandbox_path_str = str(sandbox_path)
        
        # Load execute_bash code from file and inject sandbox path
        execute_bash_code = self._load_tool_code("tool_execute_bash.py").replace("{sandbox_path_str}", sandbox_path_str)
        
        # Base sandbox tools (execute_python is not included but kept in _get_execute_python_tool())
        base_tools = [
            {
                "name": "execute_bash",
                "description": "TO RUN BASH TOOLS ALWAYS USE THIS TOOL. DO NOT EXECUTE BASH COMMANDS DIRECTLY. Execute a bash command in a sandboxed environment.",
                "text": f"The command will be executed in a sandboxed environment. The sandbox directory appears as /root/ to the LLM (e.g., 'pwd' returns /root). The actual sandbox is located at {sandbox_path_str} with filesystem and network restrictions applied. The sandbox prevents access to sensitive directories like ~/.ssh, ~/.aws, and restricts network access.",
                "tool_type": "python",
                "code": execute_bash_code,
                "variables": [
                    {
                        "name": "command",
                        "description": "The bash command to execute",
                        "required": True,
                        "type": "str"
                    },
                    {
                        "name": "timeout",
                        "description": "Maximum execution time in seconds",
                        "required": False,
                        "type": "int"
                    }
                ],
                "environment_variables": [],
                "tool_calls": []
            }
        ]
        
        # Discover dynamic tools from vmcp_tools/ directory
        # CRITICAL: Do NOT attempt discovery if sandbox directory doesn't exist.
        # This prevents accidental recreation of the directory after deletion (race condition).
        if not sandbox_path.exists():
            return base_tools

        try:
            registry = SandboxToolRegistry(sandbox_path, vmcp_id)
            discovered_tools = registry.discover_tools()
            base_tools.extend(discovered_tools)
            logger.debug(f"Discovered {len(discovered_tools)} tools from sandbox for {vmcp_id}")
        except Exception as e:
            logger.warning(f"Failed to discover sandbox tools for {vmcp_id}: {e}")
        
        return base_tools
    
    def get_sandbox_prompt(self, vmcp_id: str, vmcp_config=None) -> str:
        """
        Get sandbox setup prompt to inject into vMCP.
        
        Returns different prompts based on configuration:
        - PD enabled + sandbox disabled: Returns PD-only prompt
        - PD enabled + sandbox enabled: Returns progressive discovery prompt (with sandbox)
        - Sandbox enabled (PD disabled): Returns SDK-only prompt
        
        Args:
            vmcp_id: The vMCP ID
            vmcp_config: Optional vMCP config to check progressive discovery and sandbox flags
            
        Returns:
            Setup prompt text
        """
        # Check if progressive discovery is enabled
        progressive_discovery_enabled = False
        sandbox_enabled = False
        if vmcp_config:
            metadata = getattr(vmcp_config, 'metadata', {}) or {}
            if isinstance(metadata, dict):
                progressive_discovery_enabled = metadata.get('progressive_discovery_enabled', False) is True
                sandbox_enabled = metadata.get('sandbox_enabled', False) is True
        
        # Also check sandbox status using is_enabled method
        if not sandbox_enabled and vmcp_config:
            sandbox_enabled = self.is_enabled(vmcp_id, vmcp_config)
        
        # Select prompt based on configuration
        if progressive_discovery_enabled and not sandbox_enabled:
            # PD enabled, sandbox disabled
            prompt = self.SETUP_PROMPT_PD_ONLY
        elif progressive_discovery_enabled and sandbox_enabled:
            # PD enabled, sandbox enabled
            prompt = self.SETUP_PROMPT_PROGRESSIVE_DISCOVERY
        elif sandbox_enabled:
            # Sandbox enabled, PD disabled
            prompt = self.SETUP_PROMPT_SDK_ONLY
        else:
            # Neither enabled - return empty or default (shouldn't happen in practice)
            prompt = ""
        
        return prompt.replace("{vmcp_id}", vmcp_id)


class SandboxToolRegistry:
    """
    Discovers and manages Python scripts from sandbox as dynamic tools.
    Tools are stored in vmcp_tools/ directory and discovered on-demand.
    """
    
    def __init__(self, sandbox_path: Path, vmcp_id: str):
        self.sandbox_path = sandbox_path
        self.vmcp_id = vmcp_id
        self.tools_dir = sandbox_path / "vmcp_tools"
        self.registry_file = sandbox_path / "vmcp_tool_registry.json"
    
    def ensure_tools_directory(self) -> None:
        """Create tools directory if it doesn't exist."""
        self.tools_dir.mkdir(parents=True, exist_ok=True)
    
    def discover_tools(self) -> List[Dict[str, Any]]:
        """
        Scan vmcp_tools/ directory for Python scripts and convert to tool definitions.
        
        Returns:
            List of tool definition dictionaries compatible with custom_tools format
        """
        self.ensure_tools_directory()
        tools = []
        
        # Load registry for metadata (name, description overrides)
        registry = self._load_registry()
        
        # Scan for Python scripts
        for script_file in sorted(self.tools_dir.glob("*.py")):
            tool_def = self._parse_script_as_tool(script_file, registry)
            if tool_def:
                tools.append(tool_def)
        
        return tools
    
    def _load_registry(self) -> Dict[str, Any]:
        """Load tool registry JSON file with metadata."""
        if not self.registry_file.exists():
            return {}
        
        try:
            import json
            with open(self.registry_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load tool registry: {e}")
            return {}
    
    def _save_registry(self, registry: Dict[str, Any]) -> None:
        """Save tool registry JSON file."""
        import json
        with open(self.registry_file, 'w') as f:
            json.dump(registry, f, indent=2)
    
    def _parse_script_as_tool(
        self, 
        script_path: Path, 
        registry: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Parse Python script to extract tool definition.
        
        Looks for:
        - main() function with type hints for parameters
        - Docstring for description
        - Registry metadata for name/description overrides
        
        Returns:
            Tool definition dict or None if script is invalid
        """
        try:
            import ast
            
            # Read script content
            script_content = script_path.read_text(encoding='utf-8')
            
            # Parse AST to find main function
            tree = ast.parse(script_content)
            
            main_func = None
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == 'main':
                    main_func = node
                    break
            
            if not main_func:
                logger.debug(f"No main() function found in {script_path.name}")
                return None
            
            # Extract function signature
            tool_name = script_path.stem  # filename without .py
            description = ast.get_docstring(main_func) or f"Tool: {tool_name}"
            
            # Check registry for overrides
            if tool_name in registry:
                if 'name' in registry[tool_name]:
                    tool_name = registry[tool_name]['name']
                if 'description' in registry[tool_name]:
                    description = registry[tool_name]['description']
            
            # Extract parameters from function signature
            variables = []
            required_params = []
            
            for arg in main_func.args.args:
                if arg.arg == 'self':
                    continue
                
                param_name = arg.arg
                param_type = 'str'  # default
                
                # Extract type hint if available
                if arg.annotation:
                    if isinstance(arg.annotation, ast.Name):
                        type_name = arg.annotation.id
                        type_mapping = {
                            'str': 'str',
                            'int': 'int',
                            'float': 'float',
                            'bool': 'bool',
                            'list': 'list',
                            'dict': 'dict'
                        }
                        param_type = type_mapping.get(type_name, 'str')
                
                # Check if has default (optional parameter)
                has_default = len(main_func.args.defaults) > 0 and \
                             len(main_func.args.args) - len(main_func.args.defaults) <= \
                             main_func.args.args.index(arg)
                
                if not has_default:
                    required_params.append(param_name)
                
                variables.append({
                    'name': param_name,
                    'description': f"Parameter: {param_name}",
                    'type': param_type,
                    'required': not has_default
                })
            
            # Create tool definition
            # Read full script content for code field
            tool_def = {
                'name': tool_name,  # Keep original tool name without prefix
                'description': description,
                'tool_type': 'python',
                'code': script_content,  # Full script content
                'variables': variables,
                'environment_variables': [],
                'tool_calls': [],
                'meta': {
                    'source': 'sandbox_discovered',
                    'script_path': str(script_path.relative_to(self.sandbox_path)),
                    'vmcp_id': self.vmcp_id
                }
            }
            
            return tool_def
            
        except Exception as e:
            logger.warning(f"Failed to parse script {script_path}: {e}")
            return None
    
    def register_tool_metadata(
        self,
        tool_name: str,
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> bool:
        """
        Register metadata for a tool (name/description overrides).
        Updates vmcp_tool_registry.json.
        """
        registry = self._load_registry()
        
        if tool_name not in registry:
            registry[tool_name] = {}
        
        if name:
            registry[tool_name]['name'] = name
        if description:
            registry[tool_name]['description'] = description
        
        self._save_registry(registry)
        return True


class WorkflowManager:
    """
    Manages scheduled workflows in sandbox.
    Workflows are Python scripts stored in vmcp_workflows/ directory.
    Schedule is stored in vmcp_workflow_schedule.json.
    """
    
    def __init__(self, sandbox_path: Path, vmcp_id: str):
        self.sandbox_path = sandbox_path
        self.vmcp_id = vmcp_id
        self.workflows_dir = sandbox_path / "vmcp_workflows"
        self.schedule_file = sandbox_path / "vmcp_workflow_schedule.json"
    
    def ensure_workflows_directory(self) -> None:
        """Create workflows directory if it doesn't exist."""
        self.workflows_dir.mkdir(parents=True, exist_ok=True)
    
    def register_workflow(
        self,
        script_path: str,
        schedule: str,
        workflow_name: Optional[str] = None,
        enabled: bool = True
    ) -> bool:
        """
        Register a workflow script with schedule.
        
        Args:
            script_path: Path to Python script (relative to sandbox or absolute)
            schedule: Schedule expression - "once", "hourly", "daily", or cron expression
            workflow_name: Optional name for workflow (defaults to script filename)
            enabled: Whether workflow is enabled
        
        Returns:
            True if successful
        """
        self.ensure_workflows_directory()
        
        # Resolve script path
        script_file = Path(script_path)
        if not script_file.is_absolute():
            script_file = self.sandbox_path / script_path
        
        if not script_file.exists():
            raise FileNotFoundError(f"Workflow script not found: {script_path}")
        
        # Copy script to workflows directory
        workflow_filename = script_file.name
        target_path = self.workflows_dir / workflow_filename
        
        import shutil
        shutil.copy2(script_file, target_path)
        
        # Use provided name or derive from filename
        if not workflow_name:
            workflow_name = script_file.stem
        
        # Load schedule
        schedule_data = self._load_schedule()
        
        # Add/update workflow in schedule
        workflow_id = f"{self.vmcp_id}_{workflow_name}"
        from datetime import datetime
        schedule_data[workflow_id] = {
            'vmcp_id': self.vmcp_id,
            'workflow_name': workflow_name,
            'script_path': str(target_path.relative_to(self.sandbox_path)),
            'schedule': schedule,
            'enabled': enabled,
            'created_at': datetime.now().isoformat(),
            'last_run': None,
            'next_run': None
        }
        
        self._save_schedule(schedule_data)
        logger.info(f"Registered workflow: {workflow_name} with schedule: {schedule}")
        return True
    
    def list_workflows(self) -> List[Dict[str, Any]]:
        """List all registered workflows."""
        schedule_data = self._load_schedule()
        
        # Filter workflows for this vmcp_id
        workflows = []
        for _workflow_id, workflow_data in schedule_data.items():
            if workflow_data.get('vmcp_id') == self.vmcp_id:
                workflows.append(workflow_data)
        
        return workflows
    
    def _load_schedule(self) -> Dict[str, Any]:
        """Load workflow schedule JSON file."""
        if not self.schedule_file.exists():
            return {}
        
        try:
            import json
            with open(self.schedule_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load workflow schedule: {e}")
            return {}
    
    def _save_schedule(self, schedule: Dict[str, Any]) -> None:
        """Save workflow schedule JSON file."""
        import json
        with open(self.schedule_file, 'w') as f:
            json.dump(schedule, f, indent=2)


# Singleton instance
_sandbox_service: Optional[SandboxService] = None


def get_sandbox_service() -> SandboxService:
    """Get the singleton sandbox service instance."""
    global _sandbox_service
    if _sandbox_service is None:
        _sandbox_service = SandboxService()
    return _sandbox_service

