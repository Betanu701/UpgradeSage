"""Configuration management for UpgradeSage."""

import json
import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class UserConfig(BaseModel):
    """User-specific configuration for UpgradeSage."""
    
    # GitHub settings
    github_token: Optional[str] = Field(None, description="Optional GitHub personal access token")
    include_public_repos: bool = Field(True, description="Include public repositories in analysis")
    
    # Token usage settings
    enable_token_monitoring: bool = Field(True, description="Monitor and track token usage")
    token_usage_threshold: int = Field(80, description="Alert threshold percentage (0-100)")
    max_tokens_per_request: int = Field(120000, description="Maximum tokens per analysis request")
    
    # Analysis settings
    enable_breaking_changes_only: bool = Field(False, description="Only report breaking changes")
    include_migration_paths: bool = Field(True, description="Include suggested migration paths")
    validate_upgrade_logic: bool = Field(True, description="Ensure upgrade paths are logical")
    
    # Startup settings
    show_startup_check: bool = Field(True, description="Display startup configuration check")
    
    class Config:
        json_schema_extra = {
            "example": {
                "github_token": None,
                "include_public_repos": True,
                "enable_token_monitoring": True,
                "token_usage_threshold": 80,
                "max_tokens_per_request": 120000,
                "enable_breaking_changes_only": False,
                "include_migration_paths": True,
                "validate_upgrade_logic": True,
                "show_startup_check": True,
            }
        }


class TokenUsage(BaseModel):
    """Token usage tracking information."""
    
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    requests_count: int = 0
    
    def add_usage(self, prompt: int, completion: int) -> None:
        """Add tokens from a request."""
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.total_tokens += (prompt + completion)
        self.requests_count += 1
    
    def get_usage_percentage(self, max_tokens: int) -> float:
        """Calculate usage percentage against a threshold."""
        if max_tokens <= 0:
            return 0.0
        return (self.total_tokens / max_tokens) * 100
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "requests_count": self.requests_count,
        }


class ConfigManager:
    """Manages user configuration loading and saving."""
    
    DEFAULT_CONFIG_NAME = ".upgradesage"
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize configuration manager."""
        if config_path is None:
            # Look for config in current directory, then home directory
            current_dir = Path.cwd() / self.DEFAULT_CONFIG_NAME
            home_dir = Path.home() / self.DEFAULT_CONFIG_NAME
            
            if current_dir.exists():
                self.config_path = current_dir
            elif home_dir.exists():
                self.config_path = home_dir
            else:
                self.config_path = None
        else:
            self.config_path = config_path
        
        self._config: Optional[UserConfig] = None
        self._token_usage = TokenUsage()
    
    def load_config(self) -> UserConfig:
        """Load configuration from file or return defaults."""
        if self._config is not None:
            return self._config
        
        if self.config_path and self.config_path.exists():
            try:
                with open(self.config_path, "r") as f:
                    data = json.load(f)
                self._config = UserConfig(**data)
            except (json.JSONDecodeError, ValueError) as e:
                # If config is invalid, use defaults
                print(f"Warning: Invalid config file, using defaults: {e}")
                self._config = UserConfig()
        else:
            self._config = UserConfig()
        
        return self._config
    
    def save_config(self, config: UserConfig, path: Optional[Path] = None) -> None:
        """Save configuration to file."""
        save_path = path or self.config_path or (Path.cwd() / self.DEFAULT_CONFIG_NAME)
        
        with open(save_path, "w") as f:
            json.dump(config.model_dump(), f, indent=2)
        
        self.config_path = save_path
        self._config = config
    
    def get_token_usage(self) -> TokenUsage:
        """Get current token usage statistics."""
        return self._token_usage
    
    def record_token_usage(self, prompt_tokens: int, completion_tokens: int) -> None:
        """Record token usage from a request."""
        self._token_usage.add_usage(prompt_tokens, completion_tokens)
    
    def check_token_threshold(self) -> Optional[dict]:
        """Check if token usage exceeds threshold, return alert if needed."""
        config = self.load_config()
        
        if not config.enable_token_monitoring:
            return None
        
        percentage = self._token_usage.get_usage_percentage(config.max_tokens_per_request)
        
        if percentage >= config.token_usage_threshold:
            return {
                "alert": True,
                "message": f"Token usage at {percentage:.1f}% of configured threshold",
                "usage": self._token_usage.to_dict(),
                "threshold": config.token_usage_threshold,
            }
        
        return None
    
    def get_github_token(self) -> Optional[str]:
        """Get GitHub token from config or environment."""
        config = self.load_config()
        
        # Priority: config file > environment variable
        if config.github_token:
            return config.github_token
        
        return os.getenv("GITHUB_TOKEN")
    
    def validate_startup(self) -> dict:
        """Validate configuration at startup."""
        config = self.load_config()
        
        checks = {
            "config_loaded": self.config_path is not None,
            "config_path": str(self.config_path) if self.config_path else "Using defaults",
            "github_token_configured": bool(self.get_github_token()),
            "token_monitoring_enabled": config.enable_token_monitoring,
            "settings": {
                "include_public_repos": config.include_public_repos,
                "include_migration_paths": config.include_migration_paths,
                "validate_upgrade_logic": config.validate_upgrade_logic,
            }
        }
        
        return checks


# Global configuration manager instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """Get or create the global configuration manager."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager
