import os
from server.features.sysops_automation.sysops_contracts import SmbShareRequest
from server.features.sysops_automation.ssh_executor import shell_executor, CommandExecutionRequest

class SmbShareManager:
    SMB_CONF_DIR = "/etc/samba/conf.d"

    async def create_or_update_share(self, req: SmbShareRequest) -> bool:
        clean_name = req.share_name.strip().replace(" ", "_")
        target_path = os.path.abspath(req.directory_path)

        mkdir_req = CommandExecutionRequest(
            shell_type="bash",
            command=f"mkdir -p '{target_path}' && chmod 0777 '{target_path}'"
        )
        mkdir_res = await shell_executor.execute_command(mkdir_req)
        if not mkdir_res.success:
            return False

        conf_content = [
            f"[{clean_name}]",
            f"   path = {target_path}",
            "   browseable = yes",
            f"   read only = {'yes' if req.read_only else 'no'}",
            f"   guest ok = {'yes' if req.guest_ok else 'no'}",
            "   create mask = 0775",
            "   directory mask = 0775"
        ]
        if req.valid_users:
            conf_content.append(f"   valid users = {' '.join(req.valid_users)}")

        payload_str = "\n".join(conf_content) + "\n"
        conf_file_path = f"{self.SMB_CONF_DIR}/{clean_name}.conf"

        write_cmd = (
            f"mkdir -p {self.SMB_CONF_DIR} && "
            f"printf '%s' '{payload_str}' | tee {conf_file_path} > /dev/null && "
            f"grep -q 'include = {self.SMB_CONF_DIR}' /etc/samba/smb.conf 2>/dev/null || "
            f"echo 'include = {self.SMB_CONF_DIR}/*.conf' >> /etc/samba/smb.conf && "
            f"systemctl restart smbd || true"
        )

        apply_req = CommandExecutionRequest(shell_type="bash", command=write_cmd)
        apply_res = await shell_executor.execute_command(apply_req)
        return apply_res.success

smb_manager = SmbShareManager()
