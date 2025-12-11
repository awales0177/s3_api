"""
Service for introspecting Python libraries and extracting function documentation.
"""
import subprocess
import sys
import importlib
import inspect
import logging
import pkgutil
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
import re

logger = logging.getLogger(__name__)

class PythonIntrospectionService:
    """Service for extracting function metadata from Python libraries."""
    
    def install_package(self, package_name: str, pypi_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Install a Python package using pip.
        
        Args:
            package_name: Name of the package to install (e.g., 'pandas', 'numpy')
            pypi_url: Optional custom PyPI URL or index URL (e.g., 'https://pypi.org/simple' or 'https://custom-pypi.example.com/simple')
            
        Returns:
            dict with success status and message
        """
        try:
            logger.info(f"Installing package: {package_name}" + (f" from {pypi_url}" if pypi_url else ""))
            
            # Build pip install command
            pip_cmd = [sys.executable, "-m", "pip", "install", package_name]
            
            # Add custom PyPI URL if provided
            if pypi_url:
                # Ensure URL ends with /simple if it doesn't already
                if not pypi_url.endswith('/simple'):
                    if pypi_url.endswith('/'):
                        pypi_url = pypi_url + 'simple'
                    else:
                        pypi_url = pypi_url + '/simple'
                
                pip_cmd.extend(["--index-url", pypi_url])
                # Also add --trusted-host if it's not a standard PyPI URL
                if "pypi.org" not in pypi_url and "pypi.python.org" not in pypi_url:
                    # Extract hostname for trusted-host
                    parsed = urlparse(pypi_url)
                    if parsed.hostname:
                        pip_cmd.extend(["--trusted-host", parsed.hostname])
                        logger.info(f"Adding --trusted-host for {parsed.hostname}")
            
            result = subprocess.run(
                pip_cmd,
                capture_output=True,
                text=True,
                timeout=120  # 2 minute timeout
            )
            
            if result.returncode == 0:
                logger.info(f"Successfully installed {package_name}")
                return {
                    "success": True,
                    "message": f"Package {package_name} installed successfully",
                    "output": result.stdout
                }
            else:
                logger.error(f"Failed to install {package_name}: {result.stderr}")
                return {
                    "success": False,
                    "message": f"Failed to install {package_name}: {result.stderr}",
                    "error": result.stderr
                }
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout installing {package_name}")
            return {
                "success": False,
                "message": f"Timeout installing {package_name}",
                "error": "Installation timed out"
            }
        except Exception as e:
            logger.error(f"Error installing {package_name}: {str(e)}")
            return {
                "success": False,
                "message": f"Error installing {package_name}: {str(e)}",
                "error": str(e)
            }
    
    def parse_docstring(self, docstring: str) -> Dict[str, Any]:
        """
        Parse a docstring to extract structured information.
        
        Args:
            docstring: The docstring text
            
        Returns:
            dict with parsed docstring sections
        """
        if not docstring:
            return {
                "summary": "",
                "description": "",
                "parameters": [],
                "returns": "",
                "examples": []
            }
        
        lines = docstring.strip().split('\n')
        summary = lines[0].strip() if lines else ""
        
        # Try to extract parameters section
        params = []
        returns = ""
        description_lines = []
        in_params = False
        in_returns = False
        
        for i, line in enumerate(lines[1:], 1):
            line = line.strip()
            if not line:
                continue
                
            # Check for parameters section
            if re.match(r'^(Args|Parameters|Params):', line, re.IGNORECASE):
                in_params = True
                in_returns = False
                continue
            elif re.match(r'^(Returns|Return):', line, re.IGNORECASE):
                in_params = False
                in_returns = True
                continue
            elif re.match(r'^(Examples?|Example):', line, re.IGNORECASE):
                in_params = False
                in_returns = False
                break
            
            if in_params:
                # Try to parse parameter line: name (type): description
                param_match = re.match(r'^\s*(\w+)\s*(?:\(([^)]+)\))?\s*:?\s*(.*)', line)
                if param_match:
                    param_name = param_match.group(1)
                    param_type = param_match.group(2) or "any"
                    param_desc = param_match.group(3) or ""
                    params.append({
                        "name": param_name,
                        "type": param_type.strip(),
                        "description": param_desc.strip()
                    })
            elif in_returns:
                returns += line + " "
            elif not in_params and not in_returns:
                description_lines.append(line)
        
        return {
            "summary": summary,
            "description": "\n".join(description_lines).strip(),
            "parameters": params,
            "returns": returns.strip(),
            "examples": []
        }
    
    def get_functions_from_module(self, module_name: str) -> List[Dict[str, Any]]:
        """
        Extract functions from a Python module.
        
        Args:
            module_name: Name of the module to introspect
            
        Returns:
            List of function metadata dictionaries
        """
        try:
            logger.info(f"Importing module: {module_name}")
            module = importlib.import_module(module_name)
            
            functions = []
            
            # Get __all__ if it exists to prioritize public API
            public_api = set()
            if hasattr(module, '__all__'):
                public_api = set(module.__all__)
                logger.info(f"Module has __all__ with {len(public_api)} items")
                # Log what's in __all__ to help debug
                logger.debug(f"__all__ contains: {list(public_api)[:20]}...")  # First 20 items
            
            # Get all members of the module
            member_count = 0
            skipped_private = 0
            skipped_class = 0
            skipped_wrong_module = 0
            
            for name, obj in inspect.getmembers(module):
                member_count += 1
                
                # Skip private attributes (starting with _)
                if name.startswith('_'):
                    skipped_private += 1
                    continue
                
                # Check if it's a function (not a class)
                is_function = inspect.isfunction(obj)
                is_builtin = inspect.isbuiltin(obj)
                is_class = inspect.isclass(obj)
                
                if is_class:
                    skipped_class += 1
                    continue
                
                # Include functions and builtin functions (like pandas functions)
                # Since these are in the module's namespace, they're part of the module's API
                if is_function or is_builtin:
                    # For functions, check if they're from this module or a submodule
                    # But be lenient - if it's in the module's namespace, include it
                    if is_function and hasattr(obj, '__module__'):
                        func_module = obj.__module__
                        # Only skip if it's clearly from a different package (not a submodule)
                        if func_module and func_module != module_name:
                            # Check if it's a submodule
                            if not func_module.startswith(module_name + '.'):
                                # Check if it's from a standard library or different package
                                # Skip standard library functions that were imported
                                stdlib_modules = ('builtins', 'typing', 'collections', 'itertools', 'functools', 'operator', 'abc', 'contextlib')
                                if not func_module.startswith(stdlib_modules):
                                    skipped_wrong_module += 1
                                    logger.debug(f"Skipping {name} from module {func_module} (not {module_name} or submodule)")
                                    continue
                    
                    # For builtins (C extensions), we'll include them as they're part of the module's API
                    # These are common in libraries like pandas, numpy, etc.
                    func_module = getattr(obj, '__module__', None)
                    logger.debug(f"Processing {name} (function={is_function}, builtin={is_builtin}, module={func_module})")
                    
                    try:
                        # Get signature
                        try:
                            sig = inspect.signature(obj)
                        except (ValueError, TypeError):
                            # Some builtins don't have signatures
                            sig = None
                        
                        docstring = inspect.getdoc(obj) or ""
                        parsed_doc = self.parse_docstring(docstring)
                        
                        # Extract parameters from signature
                        parameters = []
                        if sig:
                            for param_name, param in sig.parameters.items():
                                param_type = str(param.annotation) if param.annotation != inspect.Parameter.empty else "any"
                                if param_type.startswith("<class"):
                                    param_type = param_type.split("'")[1] if "'" in param_type else "any"
                                
                                parameters.append({
                                    "name": param_name,
                                    "type": param_type,
                                    "description": next(
                                        (p["description"] for p in parsed_doc["parameters"] if p["name"] == param_name),
                                        ""
                                    ),
                                    "required": param.default == inspect.Parameter.empty,
                                    "default": str(param.default) if param.default != inspect.Parameter.empty else None
                                })
                        
                        # Get source code if available
                        try:
                            source = inspect.getsource(obj)
                        except (OSError, TypeError):
                            # Source not available (builtins, C extensions, etc.)
                            if sig:
                                source = f"def {name}{sig}:\n    # Source code not available (builtin/C extension)\n    pass"
                            else:
                                source = f"def {name}(*args, **kwargs):\n    # Source code not available (builtin/C extension)\n    pass"
                        
                        function_data = {
                            "name": name,
                            "displayName": name.replace("_", " ").title(),
                            "description": parsed_doc["summary"] or f"Function {name} from {module_name}",
                            "code": source,
                            "language": "python",
                            "parameters": parameters,
                            "usage": f"from {module_name} import {name}",
                            "dependencies": [module_name],
                            "author": f"{module_name} library",
                            "version": getattr(module, "__version__", "1.0.0"),
                            "category": "library-function",
                            "tags": [module_name, "auto-generated"],
                            "examples": []
                        }
                        
                        functions.append(function_data)
                    except Exception as e:
                        logger.warning(f"Error processing function {name}: {str(e)}")
                        continue
            
            logger.info(f"Found {len(functions)} functions in {module_name} (checked {member_count} members, skipped {skipped_private} private, {skipped_class} classes, {skipped_wrong_module} wrong module)")
            
            # If we found very few functions but there are many classes, suggest looking at submodules
            if len(functions) < 10 and skipped_class > 5:
                logger.info(f"Module has {skipped_class} classes but only {len(functions)} functions. Most functionality may be in submodules or class methods.")
            
            return functions
            
        except ImportError as e:
            logger.error(f"Failed to import {module_name}: {str(e)}")
            raise Exception(f"Module {module_name} not found. Please install it first.")
        except Exception as e:
            logger.error(f"Error introspecting {module_name}: {str(e)}")
            raise Exception(f"Error introspecting module: {str(e)}")
    
    def discover_submodules(self, module_name: str, max_depth: int = 3) -> List[str]:
        """
        Discover all submodules of a given module using multiple methods.
        
        Args:
            module_name: Name of the module to explore
            max_depth: Maximum depth to recurse (default: 3)
            
        Returns:
            List of submodule names
        """
        submodules = set()  # Use set to avoid duplicates
        visited = set()  # Track visited modules to avoid infinite loops
        
        def _discover_with_pkgutil(mod_name: str, depth: int):
            """Use pkgutil to discover submodules (more reliable for packages)."""
            if depth <= 0 or mod_name in visited:
                return
            
            visited.add(mod_name)
            
            try:
                module = importlib.import_module(mod_name)
                package_path = getattr(module, '__path__', None)
                
                if package_path:
                    # Use pkgutil to walk the package
                    for importer, modname, ispkg in pkgutil.walk_packages(package_path, prefix=mod_name + '.'):
                        if modname not in visited and modname.startswith(mod_name + '.'):
                            submodules.add(modname)
                            
                            # Recursively discover if it's a package and depth allows
                            if ispkg and depth > 1:
                                _discover_with_pkgutil(modname, depth - 1)
            except (ImportError, AttributeError, TypeError) as e:
                logger.debug(f"Error with pkgutil discovery for {mod_name}: {str(e)}")
            except Exception as e:
                logger.warning(f"Unexpected error with pkgutil for {mod_name}: {str(e)}")
        
        def _discover_with_inspect(mod_name: str, depth: int):
            """Use inspect.getmembers to discover submodules (fallback method)."""
            if depth <= 0 or mod_name in visited:
                return
            
            try:
                module = importlib.import_module(mod_name)
                
                # Get all members that might be submodules
                for name, obj in inspect.getmembers(module):
                    # Skip private attributes
                    if name.startswith('_'):
                        continue
                    
                    # Check if it's a module
                    if inspect.ismodule(obj):
                        # Check if it's a submodule of the parent
                        if hasattr(obj, '__name__'):
                            submodule_name = obj.__name__
                            # Only include if it's actually a submodule (starts with parent name)
                            if submodule_name.startswith(mod_name + '.') and submodule_name != mod_name:
                                if submodule_name not in visited:
                                    submodules.add(submodule_name)
                                    
                                    # Recursively discover submodules if depth allows
                                    if depth > 1:
                                        _discover_with_inspect(submodule_name, depth - 1)
            
            except (ImportError, AttributeError, TypeError) as e:
                logger.debug(f"Error with inspect discovery for {mod_name}: {str(e)}")
            except Exception as e:
                logger.warning(f"Unexpected error with inspect for {mod_name}: {str(e)}")
        
        try:
            # Try pkgutil first (more reliable for packages)
            _discover_with_pkgutil(module_name, max_depth)
            
            # Also try inspect method as fallback to catch modules that pkgutil might miss
            visited.clear()  # Reset visited for inspect method
            _discover_with_inspect(module_name, max_depth)
            
        except Exception as e:
            logger.warning(f"Error starting submodule discovery for {module_name}: {str(e)}")
        
        return sorted(list(submodules))  # Convert to sorted list
    
    def get_all_functions_from_package(self, package_name: str, module_path: Optional[str] = None, pypi_url: Optional[str] = None, include_submodules: bool = True) -> Dict[str, Any]:
        """
        Get all functions from a package, including all submodules.
        
        Args:
            package_name: Name of the package to install
            module_path: Optional specific module path within the package
            pypi_url: Optional custom PyPI URL
            include_submodules: Whether to include functions from submodules
            
        Returns:
            dict with installation status and list of all functions
        """
        # Install the package first
        install_result = self.install_package(package_name, pypi_url)
        
        if not install_result["success"]:
            return {
                "success": False,
                "message": install_result["message"],
                "functions": []
            }
        
        # Determine which module to import
        module_to_import = module_path if module_path else package_name
        
        all_functions = []
        modules_processed = []
        
        try:
            # Get functions from the main module
            main_functions = self.get_functions_from_module(module_to_import)
            all_functions.extend(main_functions)
            modules_processed.append(module_to_import)
            
            # If including submodules, discover and process them
            if include_submodules:
                logger.info(f"Discovering submodules of {module_to_import} (bulk mode)")
                submodules = self.discover_submodules(module_to_import, max_depth=3)
                logger.info(f"Found {len(submodules)} submodules: {submodules[:10]}{'...' if len(submodules) > 10 else ''}")
                
                for submodule in submodules:
                    try:
                        submodule_functions = self.get_functions_from_module(submodule)
                        # Add module info to each function
                        for func in submodule_functions:
                            func['source_module'] = submodule
                        all_functions.extend(submodule_functions)
                        modules_processed.append(submodule)
                    except Exception as e:
                        logger.warning(f"Error processing submodule {submodule}: {str(e)}")
                        continue
            
            return {
                "success": True,
                "message": f"Successfully extracted {len(all_functions)} functions from {len(modules_processed)} module(s)",
                "package": package_name,
                "module": module_to_import,
                "functions": all_functions,
                "modules_processed": modules_processed
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": str(e),
                "functions": []
            }
    
    def get_functions_from_package(self, package_name: str, module_path: Optional[str] = None, pypi_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Install a package and extract functions from it.
        
        Args:
            package_name: Name of the package to install
            module_path: Optional specific module path within the package (e.g., 'pandas.io' for pandas.io)
            pypi_url: Optional custom PyPI URL or index URL (e.g., 'https://pypi.org/simple' or 'https://custom-pypi.example.com/simple')
            
        Returns:
            dict with installation status and list of functions
        """
        # Install the package
        install_result = self.install_package(package_name, pypi_url)
        
        if not install_result["success"]:
            return {
                "success": False,
                "message": install_result["message"],
                "functions": []
            }
        
        # Determine which module to import
        # If module_path is provided, use it; otherwise try the package name
        module_to_import = module_path if module_path else package_name
        
        try:
            functions = self.get_functions_from_module(module_to_import)
            
            # Provide helpful suggestions for common packages
            suggestions = []
            if module_to_import == package_name:
                # Try to suggest common submodules
                common_submodules = {
                    'pandas': ['pandas.io', 'pandas.core', 'pandas.util'],
                    'numpy': ['numpy.linalg', 'numpy.random', 'numpy.fft'],
                    'requests': ['requests.api'],
                    'pyspark': ['pyspark.sql.functions', 'pyspark.sql.types', 'pyspark.ml.feature', 'pyspark.ml.classification', 'pyspark.ml.regression'],
                    'spark': ['pyspark.sql.functions', 'pyspark.sql.types'],
                }
                if package_name in common_submodules:
                    suggestions = common_submodules[package_name]
                elif package_name == 'pyspark':
                    suggestions = ['pyspark.sql.functions', 'pyspark.sql.types', 'pyspark.ml.feature']
            
            if len(functions) == 0:
                message = f"No functions found in {module_to_import}"
                if suggestions:
                    message += f". Try importing from a submodule like: {', '.join(suggestions[:2])}"
                else:
                    message += ". The module may not expose top-level functions, or they may be in submodules."
                
                return {
                    "success": True,
                    "message": message,
                    "package": package_name,
                    "module": module_to_import,
                    "functions": functions,
                    "suggestions": suggestions
                }
            
            # If we found only a few functions, suggest submodules might have more
            message = f"Successfully extracted {len(functions)} functions from {module_to_import}"
            if len(functions) < 10 and suggestions:
                message += f". For more functions, try submodules like: {', '.join(suggestions[:2])}"
            
            return {
                "success": True,
                "message": message,
                "package": package_name,
                "module": module_to_import,
                "functions": functions,
                "suggestions": suggestions if len(functions) < 10 else []
            }
        except Exception as e:
            return {
                "success": False,
                "message": str(e),
                "functions": []
            }

# Create a global instance
python_introspection_service = PythonIntrospectionService()

