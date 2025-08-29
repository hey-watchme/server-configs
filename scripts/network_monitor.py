#!/usr/bin/env python3
"""
WatchMe Network Monitor
========================
ネットワーク接続状態の監視と自動修復を行うスクリプト

使用方法:
    python3 network_monitor.py [--fix] [--json]
    
オプション:
    --fix   : 切断されたコンテナを自動的に再接続
    --json  : 結果をJSON形式で出力
"""

import docker
import json
import logging
import sys
from datetime import datetime
from typing import Dict, List, Tuple
import argparse

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/watchme-network-monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 必須コンテナのリスト
REQUIRED_CONTAINERS = [
    'watchme-scheduler-prod',
    'watchme-api-manager-prod',
    'api_gen_prompt_mood_chart',
    'api-transcriber',
    'api-gpt-v1',
    'opensmile-api',
    'opensmile-aggregator',
    'api-sed-aggregator',
    'watchme-vault-api',
    'watchme-web-prod',
    'vibe-transcriber-v2'
]

NETWORK_NAME = 'watchme-network'
EXPECTED_SUBNET = '172.27.0.0/16'


class NetworkMonitor:
    """WatchMeネットワークの監視・管理クラス"""
    
    def __init__(self):
        """Dockerクライアントを初期化"""
        try:
            self.client = docker.from_env()
            logger.info("Docker client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Docker client: {e}")
            sys.exit(1)
    
    def check_network_exists(self) -> bool:
        """ネットワークの存在確認"""
        try:
            networks = self.client.networks.list(names=[NETWORK_NAME])
            return len(networks) > 0
        except Exception as e:
            logger.error(f"Error checking network existence: {e}")
            return False
    
    def get_network_info(self) -> Dict:
        """ネットワークの詳細情報を取得"""
        try:
            network = self.client.networks.get(NETWORK_NAME)
            return {
                'id': network.id,
                'name': network.name,
                'driver': network.attrs['Driver'],
                'scope': network.attrs['Scope'],
                'subnet': network.attrs['IPAM']['Config'][0]['Subnet'] if network.attrs['IPAM']['Config'] else None,
                'gateway': network.attrs['IPAM']['Config'][0]['Gateway'] if network.attrs['IPAM']['Config'] else None,
                'created': network.attrs['Created'],
                'containers': len(network.attrs['Containers']) if network.attrs['Containers'] else 0
            }
        except Exception as e:
            logger.error(f"Error getting network info: {e}")
            return {}
    
    def get_connected_containers(self) -> List[str]:
        """接続されているコンテナのリストを取得"""
        try:
            network = self.client.networks.get(NETWORK_NAME)
            containers = network.attrs.get('Containers', {})
            return [cont['Name'] for cont in containers.values()]
        except Exception as e:
            logger.error(f"Error getting connected containers: {e}")
            return []
    
    def check_container_status(self) -> Tuple[List[str], List[str], List[str]]:
        """
        各必須コンテナの状態を確認
        
        Returns:
            (connected, disconnected, not_running) のタプル
        """
        connected = []
        disconnected = []
        not_running = []
        
        connected_containers = self.get_connected_containers()
        
        for container_name in REQUIRED_CONTAINERS:
            try:
                container = self.client.containers.get(container_name)
                
                if container.status != 'running':
                    not_running.append(container_name)
                    logger.warning(f"Container {container_name} is not running (status: {container.status})")
                elif container_name in connected_containers:
                    connected.append(container_name)
                    logger.debug(f"Container {container_name} is connected to {NETWORK_NAME}")
                else:
                    disconnected.append(container_name)
                    logger.warning(f"Container {container_name} is disconnected from {NETWORK_NAME}")
                    
            except docker.errors.NotFound:
                logger.info(f"Container {container_name} does not exist")
            except Exception as e:
                logger.error(f"Error checking container {container_name}: {e}")
        
        return connected, disconnected, not_running
    
    def connect_container(self, container_name: str) -> bool:
        """コンテナをネットワークに接続"""
        try:
            network = self.client.networks.get(NETWORK_NAME)
            container = self.client.containers.get(container_name)
            
            # 既に接続されているか確認
            network_names = [n.name for n in container.attrs['NetworkSettings']['Networks'].values()]
            if NETWORK_NAME in network_names:
                logger.info(f"Container {container_name} is already connected to {NETWORK_NAME}")
                return True
            
            # 接続実行
            network.connect(container)
            logger.info(f"Successfully connected {container_name} to {NETWORK_NAME}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect {container_name} to {NETWORK_NAME}: {e}")
            return False
    
    def fix_disconnected_containers(self, disconnected: List[str]) -> Dict[str, bool]:
        """切断されたコンテナを再接続"""
        results = {}
        
        for container_name in disconnected:
            logger.info(f"Attempting to reconnect {container_name}...")
            results[container_name] = self.connect_container(container_name)
        
        return results
    
    def generate_report(self, connected: List[str], disconnected: List[str], 
                       not_running: List[str], fix_results: Dict[str, bool] = None) -> Dict:
        """監視結果のレポートを生成"""
        network_info = self.get_network_info()
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'network': {
                'name': NETWORK_NAME,
                'exists': self.check_network_exists(),
                'info': network_info
            },
            'containers': {
                'required': len(REQUIRED_CONTAINERS),
                'connected': len(connected),
                'disconnected': len(disconnected),
                'not_running': len(not_running),
                'details': {
                    'connected': connected,
                    'disconnected': disconnected,
                    'not_running': not_running
                }
            },
            'health_status': 'healthy' if len(disconnected) == 0 and len(not_running) == 0 else 'unhealthy'
        }
        
        if fix_results:
            report['fix_results'] = fix_results
        
        return report
    
    def run(self, auto_fix: bool = False, json_output: bool = False) -> int:
        """
        監視を実行
        
        Args:
            auto_fix: 自動修復を実行するか
            json_output: JSON形式で出力するか
            
        Returns:
            終了コード (0: 成功, 1: 問題あり)
        """
        logger.info(f"Starting network monitoring for {NETWORK_NAME}")
        
        # ネットワーク存在確認
        if not self.check_network_exists():
            logger.error(f"Network {NETWORK_NAME} does not exist!")
            return 1
        
        # コンテナ状態確認
        connected, disconnected, not_running = self.check_container_status()
        
        # 自動修復
        fix_results = None
        if auto_fix and disconnected:
            logger.info(f"Auto-fix enabled. Attempting to reconnect {len(disconnected)} containers...")
            fix_results = self.fix_disconnected_containers(disconnected)
            
            # 再チェック
            connected, disconnected, not_running = self.check_container_status()
        
        # レポート生成
        report = self.generate_report(connected, disconnected, not_running, fix_results)
        
        # 出力
        if json_output:
            print(json.dumps(report, indent=2))
        else:
            self._print_report(report)
        
        # 終了コード決定
        if report['health_status'] == 'healthy':
            logger.info("Network health check completed successfully")
            return 0
        else:
            logger.warning("Network health check completed with issues")
            return 1
    
    def _print_report(self, report: Dict):
        """レポートを人間が読みやすい形式で出力"""
        print("\n" + "=" * 60)
        print("WatchMe Network Health Report")
        print("=" * 60)
        print(f"Timestamp: {report['timestamp']}")
        print(f"Network: {report['network']['name']}")
        print(f"Status: {report['health_status'].upper()}")
        
        if report['network']['info']:
            info = report['network']['info']
            print(f"\nNetwork Configuration:")
            print(f"  Subnet: {info['subnet']}")
            print(f"  Gateway: {info['gateway']}")
            print(f"  Total Containers: {info['containers']}")
        
        print(f"\nContainer Status:")
        print(f"  Required: {report['containers']['required']}")
        print(f"  Connected: {report['containers']['connected']}")
        print(f"  Disconnected: {report['containers']['disconnected']}")
        print(f"  Not Running: {report['containers']['not_running']}")
        
        if report['containers']['disconnected'] > 0:
            print(f"\nDisconnected Containers:")
            for container in report['containers']['details']['disconnected']:
                print(f"  ⚠️  {container}")
        
        if report['containers']['not_running'] > 0:
            print(f"\nNot Running Containers:")
            for container in report['containers']['details']['not_running']:
                print(f"  ❌ {container}")
        
        if 'fix_results' in report:
            print(f"\nAuto-Fix Results:")
            for container, success in report['fix_results'].items():
                status = "✅ Success" if success else "❌ Failed"
                print(f"  {container}: {status}")
        
        print("=" * 60 + "\n")


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description='WatchMe Network Monitor')
    parser.add_argument('--fix', action='store_true', help='Auto-fix disconnected containers')
    parser.add_argument('--json', action='store_true', help='Output in JSON format')
    args = parser.parse_args()
    
    monitor = NetworkMonitor()
    exit_code = monitor.run(auto_fix=args.fix, json_output=args.json)
    sys.exit(exit_code)


if __name__ == '__main__':
    main()