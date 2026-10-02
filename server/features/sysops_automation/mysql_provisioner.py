from server.features.sysops_automation.sysops_contracts import (
    MySQLProvisionRequest,
    CommandExecutionRequest
)
from server.features.sysops_automation.ssh_executor import shell_executor

class MySQLProvisioner:
    async def provision_database(self, req: MySQLProvisionRequest) -> bool:
        sql_commands = [
            f"CREATE DATABASE IF NOT EXISTS `{req.database_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;",
            f"CREATE USER IF NOT EXISTS '{req.username}'@'{req.host}' IDENTIFIED BY '{req.password}';",
            f"GRANT {req.privileges} ON `{req.database_name}`.* TO '{req.username}'@'{req.host}';",
            "FLUSH PRIVILEGES;"
        ]

        if req.initial_sql_script:
            sql_commands.append(f"USE `{req.database_name}`; {req.initial_sql_script}")

        combined_sql = " ".join(sql_commands)
        sanitized_sql = combined_sql.replace("'", "'\\''")

        cmd_str = f"mariadb -u root -e '{sanitized_sql}' || mysql -u root -e '{sanitized_sql}'"
        exec_req = CommandExecutionRequest(shell_type="bash", command=cmd_str)
        exec_res = await shell_executor.execute_command(exec_req)
        return exec_res.success

mysql_provisioner = MySQLProvisioner()
