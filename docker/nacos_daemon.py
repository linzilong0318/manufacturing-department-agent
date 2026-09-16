#!/usr/bin/env python3
"""Nacos 服务注册与心跳守护进程。

由 s6-overlay 的 nacos-registrar 服务启动，负责将容器实例注册到
Nacos 并维持心跳保活。所有日志输出到 stderr，由 s6-supervise
捕获到日志系统（/opt/data/logs/nacos-registrar/current）。

环境变量：
    NACOS_SERVER_ADDRESSES   必填，Nacos 地址，如 10.120.7.99:8848
    NACOS_NAMESPACE          Nacos 命名空间 ID，默认 ""
    NACOS_GROUP_NAME         分组名，默认 DEFAULT_GROUP
    NACOS_SERVICE_NAME        服务注册名，默认 hermes-agent
    NACOS_SERVICE_PORT        服务端口，默认 8642
    NACOS_USERNAME            Nacos 用户名，默认 nacos
    NACOS_PASSWORD            Nacos 密码，默认 nacos
    NACOS_HEARTBEAT_INTERVAL  心跳间隔（秒），默认 5
"""

from __future__ import annotations

import logging
import os
import socket
import sys
import time
from dataclasses import dataclass

from nacos import NacosClient

logger = logging.getLogger("nacos-registrar")


@dataclass
class NacosConfig:
    server_addresses: str = ""
    namespace: str = ""
    group_name: str = "DEFAULT_GROUP"
    service_name: str = "hermes-agent"
    service_port: int = 8642
    username: str = "nacos"
    password: str = "nacos"
    heartbeat_interval: float = 5.0


def _get_env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def load_config() -> NacosConfig:
    return NacosConfig(
        server_addresses=_get_env("NACOS_SERVER_ADDRESSES"),
        namespace=_get_env("NACOS_NAMESPACE"),
        group_name=_get_env("NACOS_GROUP_NAME", "DEFAULT_GROUP"),
        service_name=_get_env("NACOS_SERVICE_NAME", "hermes-agent"),
        service_port=int(_get_env("NACOS_SERVICE_PORT", "8642")),
        username=_get_env("NACOS_USERNAME", "nacos"),
        password=_get_env("NACOS_PASSWORD", "nacos"),
        heartbeat_interval=float(_get_env("NACOS_HEARTBEAT_INTERVAL", "5")),
    )


def get_container_ip() -> str:
    """通过 UDP 连接外部地址获取容器出口 IP（只触发路由，不实际发包）。"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    finally:
        sock.close()


def register_and_beat(cfg: NacosConfig) -> None:
    ip = get_container_ip()
    logger.info(
        "注册服务 %s -> %s:%s（group=%s, namespace=%s）",
        cfg.service_name,
        ip,
        cfg.service_port,
        cfg.group_name,
        cfg.namespace,
    )

    client = NacosClient(
        server_addresses=cfg.server_addresses,
        namespace=cfg.namespace or None,
        username=cfg.username,
        password=cfg.password,
    )

    client.add_naming_instance(
        service_name=cfg.service_name,
        ip=ip,
        port=cfg.service_port,
        group_name=cfg.group_name,
    )
    logger.info("服务注册成功，进入心跳循环（间隔 %ss）", cfg.heartbeat_interval)

    while True:
        client.send_heartbeat(
            service_name=cfg.service_name,
            ip=ip,
            port=cfg.service_port,
            group_name=cfg.group_name,
        )
        time.sleep(cfg.heartbeat_interval)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
    )

    cfg = load_config()
    if not cfg.server_addresses:
        logger.error("NACOS_SERVER_ADDRESSES 未配置，Nacos 注册已跳过。")
        return 1

    while True:
        try:
            register_and_beat(cfg)
        except KeyboardInterrupt:
            logger.info("收到终止信号，退出 Nacos 心跳守护。")
            return 0
        except Exception:
            logger.exception("注册/心跳异常，1s 后重试。")
            time.sleep(1)


if __name__ == "__main__":
    sys.exit(main())
