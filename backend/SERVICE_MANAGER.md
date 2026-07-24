# SERVICE_MANAGER.md — OX-HOUSE-OS-1 Phase 2
Long-lived subsystems are supervised as Services with a uniform lifecycle:
`start() / stop() / restart() / health()`; state ∈ {stopped, running, error}.

Built-ins (thin wrappers — they do NOT reimplement the subsystem):
| Service | Wraps | health() |
|---|---|---|
| runtime | Runtime Kernel | instances, pools, sessions |
| workflow | workflow engine | engine phases |
| memory | data dir | data_dir, exists |
| monitoring | reliability_dashboard | gpu present/util |
| scheduler | daemon job runner (0.2s tick) | registered jobs |

ServiceManager: register / register_defaults / start_all / stop_all / health /
start(name) / stop / restart. API: `GET /api/os/services`,
`POST /api/os/services/{name}/{start|stop|restart}`.
