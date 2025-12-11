import os
import csv
import json
from datetime import datetime

# 基础数据存储路径
BASE_DIR = os.path.join(os.getcwd(), "match_data")


class StorageManager:
    def __init__(self):
        if not os.path.exists(BASE_DIR):
            os.makedirs(BASE_DIR)

        self.current_project_path = None
        # 移除文件句柄缓存，避免多组别切换时文件占用问题，改用每次写入打开关闭(性能对于计分系统足够)

    def create_project(self, project_name, mode):
        """
        创建项目文件夹
        结构: match_data/{Timestamp}_{ProjectName}/
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # 简单的文件名清洗，防止非法字符
        safe_name = "".join([c for c in project_name if c.isalnum() or c in (' ', '_', '-')]).strip()
        folder_name = f"{timestamp}_{safe_name}"

        self.current_project_path = os.path.join(BASE_DIR, folder_name)
        os.makedirs(self.current_project_path, exist_ok=True)

        # 初始化项目配置
        config = {
            "project_name": project_name,
            "mode": mode,
            "created_at": timestamp,
            "groups": []
        }
        self.save_config(config)
        return config

    def save_config(self, config_data):
        if not self.current_project_path: return
        path = os.path.join(self.current_project_path, "config.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)

    def _get_group_dir(self, group_name):
        """获取(并创建)组别子文件夹"""
        if not self.current_project_path or not group_name:
            return self.current_project_path  # 以此防守，如果没有组名则存根目录

        # 清洗组名防止路径穿越
        safe_group = "".join([c for c in group_name if c.isalnum() or c in (' ', '_', '-')]).strip()
        if not safe_group: safe_group = "Default_Group"

        group_path = os.path.join(self.current_project_path, safe_group)
        if not os.path.exists(group_path):
            os.makedirs(group_path)
        return group_path

    def init_referee_log(self, group_name, ref_index, role):
        """初始化日志文件 (写入表头)"""
        if not self.current_project_path: return

        group_dir = self._get_group_dir(group_name)
        filename = f"referee_{ref_index}_{role}.csv"
        filepath = os.path.join(group_dir, filename)

        if not os.path.exists(filepath):
            with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "SystemTime", "BLE_Timestamp", "DeviceRole",
                    "Contestant", "CurrentTotal", "EventType",
                    "TotalPlus", "TotalMinus"
                ])
        return filepath

    def log_data(self, group_name, ref_index, role, packet, contestant_name):
        """
        记录数据到: match_data/项目/组别/referee_x.csv
        """
        if not self.current_project_path: return

        # 1. 确保目录和文件存在
        filepath = self.init_referee_log(group_name, ref_index, role)

        # 2. 解析数据
        current_total, event_type, total_plus, total_minus, ble_timestamp = packet
        system_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        # 3. 追加写入
        try:
            with open(filepath, 'a', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow([
                    system_time,
                    ble_timestamp,
                    role,
                    contestant_name,
                    current_total,
                    event_type,
                    total_plus,
                    total_minus
                ])
        except Exception as e:
            print(f"[Storage Error] {e}")

    def list_projects(self):
        """列出所有历史项目"""
        projects = []
        if not os.path.exists(BASE_DIR):
            return []

        # 按修改时间倒序排列
        dirs = sorted(os.listdir(BASE_DIR), key=lambda x: os.path.getmtime(os.path.join(BASE_DIR, x)), reverse=True)

        for d in dirs:
            path = os.path.join(BASE_DIR, d)
            config_path = os.path.join(path, "config.json")
            if os.path.isdir(path) and os.path.exists(config_path):
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        cfg = json.load(f)
                        # 补充文件夹名称以便后续加载
                        cfg['dir_name'] = d
                        projects.append(cfg)
                except:
                    pass
        return projects

    def load_project_config(self, dir_name):
        """加载指定项目的配置"""
        path = os.path.join(BASE_DIR, dir_name)
        config_path = os.path.join(path, "config.json")
        if os.path.exists(config_path):
            self.current_project_path = path  # 恢复上下文路径
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None

    def load_report_data(self, dir_name):
        """
        解析 CSV 生成报表数据
        返回结构: {
            "GroupName": {
                "ContestantName": {
                    "RefereeIndex": { "total": 10, "plus": 10, "minus": 0 }
                }
            }
        }
        """
        project_path = os.path.join(BASE_DIR, dir_name)
        if not os.path.exists(project_path): return {}

        report = {}

        # 遍历该项目下的所有组别文件夹
        for group_name in os.listdir(project_path):
            group_path = os.path.join(project_path, group_name)
            if not os.path.isdir(group_path): continue

            report[group_name] = {}

            # 遍历该组别下的所有 CSV (referee_X_PRIMARY.csv)
            for file in os.listdir(group_path):
                if not file.endswith(".csv"): continue

                # 解析文件名: referee_{index}_{role}.csv
                parts = file.replace(".csv", "").split("_")
                if len(parts) < 3: continue

                ref_idx = int(parts[1])
                role = parts[2]

                # 我们主要读取 PRIMARY 的数据作为总分依据（如果是双机模式，CSV里记录的 CurrentTotal已经是计算过的）
                # 但为了严谨，我们应该读取对应的 role。
                # 简化逻辑：在这个系统中，referee.py 写入日志时，current_total 已经是该裁判视角的总分
                # 我们只需要取每个选手在该文件中的“最后一条”记录即可

                file_path = os.path.join(group_path, file)

                # 临时存储该文件里每个选手的最新状态
                latest_records = {}

                try:
                    with open(file_path, 'r', encoding='utf-8-sig') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            c_name = row.get("Contestant")
                            if not c_name: continue

                            # 更新为最后一行（覆盖前面的）
                            latest_records[c_name] = {
                                "total": int(row.get("CurrentTotal") or 0),
                                "plus": int(row.get("TotalPlus") or 0),
                                "minus": int(row.get("TotalMinus") or 0)
                            }
                except Exception as e:
                    print(f"Error reading {file}: {e}")
                    continue

                # 合并到大表
                for c_name, score_data in latest_records.items():
                    if c_name not in report[group_name]:
                        report[group_name][c_name] = {}

                    # 这里的逻辑是：如果是双机模式，我们会有 PRIMARY 和 SECONDARY 两个文件
                    # 但在 logic/referee.py 中，我们是分别记录的。
                    # 为了生成总分表，我们应该主要信任 PRIMARY 的 CurrentTotal (因为它是计算后的结果，或者我们自己在这里聚合)
                    # 简单起见，如果 role 是 PRIMARY，直接采纳；如果是 SECONDARY，可能只记录了扣分细节
                    # 既然 logic/referee.py 里 _update_score_output 算出了最终 Total，
                    # 且 log_data 记录的是当时的 snapshot。
                    # 如果是双机，Primary 的 CurrentTotal = Pri_Plus - Sec_Plus (即最终分)
                    # 所以我们只读取 PRIMARY 文件的 total 即可代表该裁判的最终给分。

                    if role == "PRIMARY":
                        report[group_name][c_name][ref_idx] = score_data
                    elif role == "SECONDARY":
                        # 如果需要展示副设备细节，可以在这里合并，暂时略过，以主设备记录的总分为准
                        pass

        return report

    def get_scored_players(self, group_name):
        """
        获取指定组别下所有已有成绩记录的选手名单
        """
        if not self.current_project_path: return []

        # 使用 _get_group_dir 确保路径正确（复用现有逻辑）
        group_dir = self._get_group_dir(group_name)
        if not os.path.exists(group_dir):
            return []

        scored_contestants = set()

        try:
            # 遍历该组文件夹下的所有 CSV
            for filename in os.listdir(group_dir):
                if not filename.endswith(".csv"): continue

                filepath = os.path.join(group_dir, filename)
                with open(filepath, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        c_name = row.get("Contestant")
                        # 只要有记录就视为已打分
                        if c_name:
                            scored_contestants.add(c_name)
        except Exception as e:
            print(f"Error scanning scored players: {e}")

        return list(scored_contestants)

storage_manager = StorageManager()