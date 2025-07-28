"""
Strategy Validator - Validates custom strategy code for security and correctness
"""

import ast
import os
from typing import List, Tuple, Set
import logging

logger = logging.getLogger(__name__)


class StrategyValidator:
    """
    Validates custom strategy files for security and correctness.
    """
    
    # Dangerous modules that should not be imported
    FORBIDDEN_MODULES = {
        'os', 'sys', 'subprocess', 'shutil', 'tempfile',
        'pickle', 'marshal', 'eval', 'exec', 'compile',
        'importlib', '__import__', 'globals', 'locals',
        'vars', 'dir', 'hasattr', 'getattr', 'setattr',
        'delattr', 'socket', 'urllib', 'http', 'ftplib',
        'smtplib', 'poplib', 'imaplib', 'telnetlib',
        'ctypes', 'threading', 'multiprocessing',
        'asyncio', 'concurrent'
    }
    
    # Allowed modules for strategy development
    ALLOWED_MODULES = {
        'math', 'statistics', 'random', 'datetime', 'time',
        'decimal', 'fractions', 'collections', 'itertools',
        'functools', 'operator', 'copy', 'json', 'csv',
        'logging', 'typing', 'abc', 'dataclasses',
        'numpy', 'pandas', 'ta', 'talib', 'scipy',
        'matplotlib', 'seaborn', 'plotly', 'requests'
    }
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
    
    def validate_file(self, file_path: str) -> Tuple[bool, List[str], List[str]]:
        """
        Validate a strategy file.
        
        Args:
            file_path: Path to the strategy file
            
        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        self.errors = []
        self.warnings = []
        
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                self.errors.append(f"File does not exist: {file_path}")
                return False, self.errors, self.warnings
            
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse the AST
            try:
                tree = ast.parse(content)
            except SyntaxError as e:
                self.errors.append(f"Syntax error: {str(e)}")
                return False, self.errors, self.warnings
            
            # Validate the AST
            self._validate_ast(tree)
            
            # Check for required elements
            self._check_required_elements(tree)
            
            return len(self.errors) == 0, self.errors, self.warnings
            
        except Exception as e:
            self.errors.append(f"Validation error: {str(e)}")
            return False, self.errors, self.warnings
    
    def _validate_ast(self, tree: ast.AST):
        """
        Validate the AST for security issues.
        
        Args:
            tree: Parsed AST
        """
        for node in ast.walk(tree):
            self._check_imports(node)
            self._check_dangerous_functions(node)
            self._check_file_operations(node)
            self._check_network_operations(node)
    
    def _check_imports(self, node: ast.AST):
        """
        Check import statements for forbidden modules.
        
        Args:
            node: AST node to check
        """
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_name = alias.name.split('.')[0]  # Get root module
                if module_name in self.FORBIDDEN_MODULES:
                    self.errors.append(f"Forbidden import: {alias.name}")
                elif module_name not in self.ALLOWED_MODULES:
                    self.warnings.append(f"Unknown module: {alias.name} - proceed with caution")
        
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                module_name = node.module.split('.')[0]  # Get root module
                if module_name in self.FORBIDDEN_MODULES:
                    self.errors.append(f"Forbidden import from: {node.module}")
                elif module_name not in self.ALLOWED_MODULES:
                    self.warnings.append(f"Unknown module: {node.module} - proceed with caution")
    
    def _check_dangerous_functions(self, node: ast.AST):
        """
        Check for dangerous function calls.
        
        Args:
            node: AST node to check
        """
        dangerous_functions = {
            'eval', 'exec', 'compile', '__import__',
            'globals', 'locals', 'vars', 'dir',
            'getattr', 'setattr', 'delattr', 'hasattr'
        }
        
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in dangerous_functions:
                    self.errors.append(f"Dangerous function call: {node.func.id}")
    
    def _check_file_operations(self, node: ast.AST):
        """
        Check for file system operations.
        
        Args:
            node: AST node to check
        """
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in ['open', 'file']:
                    self.warnings.append("File operation detected - ensure it's necessary")
            elif isinstance(node.func, ast.Attribute):
                if (isinstance(node.func.value, ast.Name) and 
                    node.func.value.id == 'os' and 
                    node.func.attr in ['remove', 'rmdir', 'unlink', 'rename']):
                    self.errors.append(f"Dangerous file operation: os.{node.func.attr}")
    
    def _check_network_operations(self, node: ast.AST):
        """
        Check for network operations.
        
        Args:
            node: AST node to check
        """
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                # Allow requests module for API calls
                if (isinstance(node.func.value, ast.Name) and 
                    node.func.value.id == 'requests'):
                    # This is allowed for API calls
                    pass
                elif (hasattr(node.func.value, 'id') and 
                      node.func.value.id in ['socket', 'urllib', 'http']):
                    self.errors.append(f"Direct network operation not allowed: {node.func.value.id}")
    
    def _check_required_elements(self, tree: ast.AST):
        """
        Check for required elements in the strategy.
        
        Args:
            tree: Parsed AST
        """
        has_base_import = False
        has_strategy_class = False
        has_execute_method = False
        
        for node in ast.walk(tree):
            # Check for BaseStrategy import
            if isinstance(node, ast.ImportFrom):
                if (node.module and 
                    'base_strategy' in node.module and 
                    any(alias.name == 'BaseStrategy' for alias in node.names)):
                    has_base_import = True
            
            # Check for strategy class
            if isinstance(node, ast.ClassDef):
                # Check if class inherits from BaseStrategy
                for base in node.bases:
                    if isinstance(base, ast.Name) and base.id == 'BaseStrategy':
                        has_strategy_class = True
                        
                        # Check for execute method
                        for item in node.body:
                            if (isinstance(item, ast.FunctionDef) and 
                                item.name == 'execute'):
                                has_execute_method = True
        
        if not has_base_import:
            self.errors.append("Strategy must import BaseStrategy")
        
        if not has_strategy_class:
            self.errors.append("Strategy must define a class inheriting from BaseStrategy")
        
        if not has_execute_method:
            self.errors.append("Strategy class must implement execute() method")
    
    def validate_code_string(self, code: str) -> Tuple[bool, List[str], List[str]]:
        """
        Validate a code string directly.
        
        Args:
            code: Python code string to validate
            
        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        self.errors = []
        self.warnings = []
        
        try:
            # Parse the code
            tree = ast.parse(code)
            
            # Validate the AST
            self._validate_ast(tree)
            self._check_required_elements(tree)
            
            return len(self.errors) == 0, self.errors, self.warnings
            
        except SyntaxError as e:
            self.errors.append(f"Syntax error: {str(e)}")
            return False, self.errors, self.warnings
        except Exception as e:
            self.errors.append(f"Validation error: {str(e)}")
            return False, self.errors, self.warnings