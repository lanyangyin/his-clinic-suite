# Linux 与 Termux 部署文档索引

请按目标系统选择独立文档：

- [Linux 独立部署指南（从第 0 步到可用）](Linux部署指南.md)
- [Android Termux 独立部署指南（从第 0 步到可用）](Termux部署指南.md)
- [桌面客户端部署指南（Windows 为主）](客户端部署指南.md)

## 结论

- Linux：推荐，已用 WSL Ubuntu 24.04 / Python 3.12 实测。
- Termux + Ubuntu：可以，适合小门诊/演示/备用；proot 免 root，chroot 需要 root。
- 服务端不需要 PySide6；源码/备份可放 `/sdcard`；数据库优先内部，sdcard 模式需 DELETE 日志。
- 详细限制、备份、systemd、保活、故障排查见上面两份独立文档。
