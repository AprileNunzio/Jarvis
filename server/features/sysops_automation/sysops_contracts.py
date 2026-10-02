from typing import Dict, List, Optional
from pydantic import BaseModel, Field

class CommandExecutionRequest(BaseModel):
    shell_type: str
    command: str
    target_host: Optional[str] = None
    ssh_user: Optional[str] = None
    ssh_port: int = 22
    timeout_seconds: int = 60

class CommandExecutionResult(BaseModel):
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float

class SmbShareRequest(BaseModel):
    share_name: str
    directory_path: str
    read_only: bool = False
    guest_ok: bool = False
    valid_users: List[str] = Field(default_factory=list)

class MySQLProvisionRequest(BaseModel):
    database_name: str
    username: str
    password: str
    host: str = "localhost"
    privileges: str = "ALL PRIVILEGES"
    initial_sql_script: Optional[str] = None

class AppScaffoldRequest(BaseModel):
    app_name: str
    template_type: str
    target_directory: str
    environment_variables: Dict[str, str] = Field(default_factory=dict)
