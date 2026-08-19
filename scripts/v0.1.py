#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
自动挂号脚本 - 适用于指定诊所的预约挂号系统
流程：
1. 查询有号日期
2. 选择日期
3. 获取医生列表并选择医生
4. 选择上午/下午
5. 获取该时段号源列表并选择具体时间段
6. 等待到放号前45秒，锁定号源
7. 等待到放号后45秒，提交订单
"""

import requests
import json
import datetime
import time
import sys
import re
import os
from dotenv import load_dotenv
from typing import Dict, List, Optional, Any
# ==================== 配置区域（用户需填写） ====================
# 以下信息可通过输入或从环境变量读取，此处留空供运行时输入
BASE_URL = ""                              # API 基础地址
AUTHORIZATION = ""                         # Authorization 令牌（可从抓包获得）
CLINIC_ID = ""                             # 诊所ID
USER_ID = ""                               # 用户ID（锁定和下单时使用）
MEMBER_ID = ""                             # 就诊人ID（下单时需要）
PAT_NAME = ""                              # 患者姓名
PAT_SEX = ""                               # 性别（如"男"）
PAT_BIRTHDAY = ""                          # 生日（格式"2006-12-01"）
PAT_ID_NUMBER = ""                         # 身份证号（可选）
PAT_ADDRESS = ""                           # 地址（可选）
ALLERGIES = "暂无过敏史"                    # 过敏史
# ================================================================

class RegistrationBot:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url
        self.session = requests.Session()
        # 通用请求头
        self.session.headers.update({
            "Authorization": token,
            "Cb-Client": "cb-ihospital-wx",
            "Cb-Version": "cbjy-mini-app@6.1.0",
            "Charset": "utf-8",
            "Referer": "https://servicewechat.com/wxcab6b298816d6b65/167/page-frame.html",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
            "Accept-Encoding": "gzip, deflate, br",
        })
        # 存储用户选择
        self.selected_date = None           # 日期字符串 "2026-08-19"
        self.selected_doc = None            # 医生信息字典
        self.selected_type = None           # 1上午 / 2下午
        self.selected_source = None         # 号源信息字典（含sourceId）
        self.release_time = None            # 放号时间 datetime 对象
        self.lock_response = None           # 锁定接口返回

    def _get(self, path: str, params: Dict = None) -> Dict:
        """发送GET请求并返回JSON"""
        url = f"{self.base_url}{path}"
        resp = self.session.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, data: Dict = None) -> Dict:
        """发送POST请求（JSON）并返回JSON"""
        url = f"{self.base_url}{path}"
        resp = self.session.post(url, json=data)
        resp.raise_for_status()
        return resp.json()

    # -------------------- 步骤1：查询有号日期 --------------------
    def get_available_dates(self, clinic_id: str, start_date: str, end_date: str) -> List[str]:
        """
        调用接口 /cbyzs-scheduler/opsource/v1/getClinicSourceWeek
        返回有号的日期列表（hasSource=1）
        """
        path = "/cbyzs-scheduler/opsource/v1/getClinicSourceWeek"
        params = {
            "clinicId": clinic_id,
            "sdate": start_date,
            "edate": end_date
        }
        result = self._get(path, params)
        if result.get("code") != 0:
            raise Exception(f"查询号源失败: {result.get('msg')}")
        data_list = result.get("data", [])
        # 过滤有号的日期
        available = [item["date"] for item in data_list if item.get("hasSource") == 1]
        return available

    # -------------------- 步骤2：获取医生列表 --------------------
    def get_doctor_list(self, clinic_id: str, search_date: str = "") -> List[Dict]:
        """
        调用接口 /cbyzs-scheduler/v1/appointRegister/getDocListByClinicIdV2
        返回医生列表（包含sourceDayList）
        """
        path = "/cbyzs-scheduler/v1/appointRegister/getDocListByClinicIdV2"
        params = {
            "clinicId": clinic_id,
            "current": 1,
            "size": 100,
            "searchDate": search_date   # 如果传空则返回全部
        }
        result = self._get(path, params)
        if result.get("code") != 0:
            raise Exception(f"获取医生列表失败: {result.get('msg')}")
        records = result.get("data", {}).get("records", [])
        return records

    # -------------------- 步骤3：获取号源ID列表 --------------------
    def get_source_list(self, date: str, doc_id: str, type_code: int) -> List[Dict]:
        """
        调用接口 /cbyzs-scheduler/opsource/v1/getDocNoonSource
        返回该医生某天某时段的号源列表
        """
        path = "/cbyzs-scheduler/opsource/v1/getDocNoonSource"
        params = {
            "date": date,
            "docId": doc_id,
            "type": type_code
        }
        result = self._get(path, params)
        if result.get("code") != 0:
            raise Exception(f"获取号源列表失败: {result.get('msg')}")
        return result.get("data", [])

    # -------------------- 步骤4：检查是否有锁定的号源 --------------------
    def check_lock(self, user_id: str) -> Optional[Dict]:
        """
        调用接口 /cbyzs-mobile-doctor-backend/hospitalOrder/scheduleLockCheck
        返回当前锁定的号源信息，若无锁定则返回None
        """
        path = "/cbyzs-mobile-doctor-backend/hospitalOrder/scheduleLockCheck"
        params = {"userId": user_id}
        result = self._get(path, params)
        if result.get("code") != 0:
            # 若返回错误，可能没有锁定，视为无锁定
            return None
        data = result.get("data")
        if data and data.get("sourceId"):
            return data
        return None

    # -------------------- 步骤5：锁定号源 --------------------
    def lock_source(self, user_id: str, source_id: str) -> Dict:
        """
        调用接口 /cbyzs-mobile-doctor-backend/hospitalOrder/scheduleLock
        锁定指定的号源
        """
        path = "/cbyzs-mobile-doctor-backend/hospitalOrder/scheduleLock"
        payload = {
            "userId": user_id,
            "sourceId": source_id
        }
        result = self._post(path, payload)
        if result.get("code") != 0:
            raise Exception(f"锁定号源失败: {result.get('msg')}")
        return result.get("data", {})

    # -------------------- 步骤6：提交订单 --------------------
    def add_order(self, order_data: Dict) -> Dict:
        """
        调用接口 /cbyzs-mobile-doctor-backend/hospitalOrder/addVisitOrder
        提交预约订单
        """
        path = "/cbyzs-mobile-doctor-backend/hospitalOrder/addVisitOrder"
        result = self._post(path, order_data)
        if result.get("code") != 0:
            raise Exception(f"提交订单失败: {result.get('msg')}")
        return result.get("data", {})

    # -------------------- 辅助：解析放号时间 --------------------
    @staticmethod
    def parse_release_time(config_str: str, date_str: str) -> datetime.datetime:
        """
        从config字符串（如"08月19日07:00放号"）和日期（"2026-08-19"）解析出放号时间
        返回datetime对象
        """
        # 提取时间部分 "07:00"
        match = re.search(r'(\d{2}:\d{2})', config_str)
        if not match:
            raise ValueError(f"无法从config解析时间: {config_str}")
        time_part = match.group(1)  # "07:00"
        # 组合日期和时间
        dt_str = f"{date_str} {time_part}:00"
        return datetime.datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")

    # -------------------- 主流程 --------------------
    def run(self, clinic_id: str, user_id: str, member_id: str, patient_info: Dict):
        """
        执行完整挂号流程
        patient_info: 包含 patName, sex, birthday, idNumber, address, allergies 等
        """
        # ----- 1. 查询有号日期 -----
        today = datetime.date.today()
        start_date = today.strftime("%Y-%m-%d")
        end_date = (today + datetime.timedelta(days=7)).strftime("%Y-%m-%d")
        print(f"查询 {start_date} 至 {end_date} 期间的号源...")
        available = self.get_available_dates(clinic_id, start_date, end_date)
        if not available:
            print("当前时间段内无号源，程序退出。")
            return
        print("有号的日期：")
        for idx, d in enumerate(available):
            print(f"  {idx+1}. {d}")
        choice = int(input("请选择日期编号: ")) - 1
        self.selected_date = available[choice]
        print(f"已选择日期: {self.selected_date}")

        # ----- 2. 获取医生列表并选择 -----
        print("正在获取医生列表...")
        doctors = self.get_doctor_list(clinic_id, self.selected_date)
        if not doctors:
            print("未找到医生信息，程序退出。")
            return
        print("可选医生：")
        for idx, doc in enumerate(doctors):
            name = doc.get("docName", "未知")
            dept = doc.get("deptName", "")
            print(f"  {idx+1}. {name} ({dept})")
        choice_doc = int(input("请选择医生编号: ")) - 1
        self.selected_doc = doctors[choice_doc]
        doc_id = self.selected_doc["docId"]
        print(f"已选择医生: {self.selected_doc['docName']}")

        # ----- 3. 选择上午/下午 -----
        # 从该医生的sourceDayList中提取当前日期的号源信息
        source_day_list = self.selected_doc.get("sourceDayList", [])
        # 过滤出所选日期的条目
        day_info_list = [item for item in source_day_list if item.get("date") == self.selected_date]
        if not day_info_list:
            print(f"该医生在 {self.selected_date} 没有排班，程序退出。")
            return
        # 显示可用的type（1上午，2下午）
        print("可选的时段：")
        for item in day_info_list:
            type_code = item.get("type")
            if type_code == 0:
                continue  # 无号
            desc = "上午" if type_code == 1 else "下午" if type_code == 2 else f"未知({type_code})"
            config = item.get("config", "")
            visit_num = item.get("visitNumber", 0)
            print(f"  {type_code}. {desc} (剩余号数: {visit_num}, 放号时间: {config})")
        type_choice = int(input("请选择时段编号 (1上午/2下午): "))
        self.selected_type = type_choice
        # 获取该时段的配置（放号时间）
        target_day_info = next((item for item in day_info_list if item.get("type") == type_choice), None)
        if not target_day_info:
            print("选择的时段无效。")
            return
        config_str = target_day_info.get("config", "")
        if not config_str:
            print("该时段无放号时间配置，程序退出。")
            return
        # 解析放号时间
        self.release_time = self.parse_release_time(config_str, self.selected_date)
        print(f"放号时间: {self.release_time.strftime('%Y-%m-%d %H:%M:%S')}")

        # ----- 4. 获取号源列表并选择具体时间段 -----
        print("正在获取号源列表...")
        sources = self.get_source_list(self.selected_date, doc_id, type_choice)
        if not sources:
            print("该时段无可用号源，程序退出。")
            return
        print("可选号源（时间段）：")
        for idx, src in enumerate(sources):
            start = src.get("stratTime", "")
            end = src.get("endTime", "")
            print(f"  {idx+1}. {start} - {end}")
        choice_src = int(input("请选择号源编号: ")) - 1
        self.selected_source = sources[choice_src]
        source_id = self.selected_source["sourceId"]
        print(f"已选择号源ID: {source_id}")

        # -----构造订单数据-----
        order_data = {
            "userId": user_id,
            "address": patient_info.get("address", ""),
            "birthday": patient_info.get("birthday", ""),
            "cityCode": "",
            "cityName": "",
            "countyCode": "",
            "countyName": "",
            "idNumber": patient_info.get("idNumber", ""),
            "patSex": patient_info.get("sex", ""),
            "provCode": "",
            "provName": "",
            "relationCode": "",
            "relationName": "",
            "sexCode": 1 if patient_info.get("sex") == "男" else 0,
            "allergies": patient_info.get("allergies", "暂无过敏史"),
            "clinicId": clinic_id,
            "deptId": self.selected_doc.get("deptId", ""),
            "deptName": self.selected_doc.get("deptName", ""),
            "docId": doc_id,
            "docName": self.selected_doc.get("docName", ""),
            "filelist": [],
            "memberId": member_id,
            "patName": patient_info.get("patName", ""),
            "sourceDetailId": "",   # 通常为空
            "sourceId": source_id,
            "symptoms": "",
            "temperature": "",
            "regFee": "0",
            "couponPackageId": ""
        }

        # -----根据选择执行不同操作-----
        print("1. 放号前45s锁定号源，放号后45s提交预约\n2. 立即锁定号源并提交预约")
        sessionChoice = int(input("请选择操作："))
        if sessionChoice == 1:
            # ----- 5. 等待至放号前45秒，执行锁定 -----
            now = datetime.datetime.now()
            lock_time = self.release_time - datetime.timedelta(seconds=45)
            if lock_time > now:
                wait_seconds = (lock_time - now).total_seconds()
                print(f"等待 {wait_seconds:.1f} 秒后开始锁定（放号前45秒）...")
                time.sleep(wait_seconds)
            else:
                print("当前时间已晚于放号前45秒，立即尝试锁定。")

            # 锁定前检查是否已有锁定（可选）
            locked = self.check_lock(user_id)
            if locked:
                print(f"检测到已锁定号源: {locked.get('sourceId')}，将先解锁? (本脚本不处理解锁，请手动处理)")
                # 注意：本脚本不实现解锁，若已有锁定可能影响后续操作，可选择退出或继续覆盖锁定（可能失败）
                # 这里我们直接尝试锁定，若失败则退出
            print("正在锁定号源...")
            lock_resp = self.lock_source(user_id, source_id)
            self.lock_response = lock_resp
            print(f"锁定成功，过期时间: {lock_resp.get('expireTime')}")

            # ----- 6. 等待至放号后45秒，提交订单 -----
            submit_time = self.release_time + datetime.timedelta(seconds=45)
            now = datetime.datetime.now()
            if submit_time > now:
                wait_seconds = (submit_time - now).total_seconds()
                print(f"等待 {wait_seconds:.1f} 秒后提交订单（放号后45秒）...")
                time.sleep(wait_seconds)
            else:
                print("当前时间已晚于放号后45秒，立即提交订单。")

            print("正在提交订单...")
            order_resp = self.add_order(order_data)
            print("订单提交成功！")
            print(f"订单号: {order_resp.get('orderNumber')}")
            print(f"订单状态: {order_resp.get('orderStatus')}")
        else:
            # 锁定前检查是否已有锁定（可选）
            locked = self.check_lock(user_id)
            if locked:
                print(f"检测到已锁定号源: {locked.get('sourceId')}，将先解锁? (本脚本不处理解锁，请手动处理)")
                # 注意：本脚本不实现解锁，若已有锁定可能影响后续操作，可选择退出或继续覆盖锁定（可能失败）
                # 这里我们直接尝试锁定，若失败则退出
            print("正在锁定号源...")
            lock_resp = self.lock_source(user_id, source_id)
            self.lock_response = lock_resp
            print(f"锁定成功，过期时间: {lock_resp.get('expireTime')}")

            # -----提交订单-----
            print("正在提交订单...")
            order_resp = self.add_order(order_data)
            print("订单提交成功！")
            print(f"订单号: {order_resp.get('orderNumber')}")
            print(f"订单状态: {order_resp.get('orderStatus')}")


def main():
    # 从用户输入获取必要参数（也可从配置文件读取）
    load_dotenv()
    print("请准备以下信息（或从环境变量获取）：")
    BASE_URL = os.getenv("BASE_URL") or input ("请输入BASE_URL: ").strip()
    token = os.getenv("AUTHORIZATION") or input("请输入 Authorization 令牌: ").strip()
    clinic_id = os.getenv("CLINIC_ID") or input("请输入诊所ID (clinicId): ").strip()
    user_id = os.getenv("USER_ID") or input("请输入用户ID (userId): ").strip()
    member_id = os.getenv("MEMBER_ID") or input("请输入就诊人ID (memberId): ").strip()
    pat_name = os.getenv("PAT_NAME") or input("请输入患者姓名: ").strip()
    pat_sex = os.getenv("PAT_SEX") or input("请输入患者性别 (男/女): ").strip()
    pat_birthday = os.getenv("PAT_BIRTHDAY") or input("请输入患者生日 (格式 2006-12-01): ").strip()
    pat_id = os.getenv("PAT_ID_NUMBER") or input("请输入身份证号 (可选，直接回车跳过): ").strip()
    pat_address = os.getenv("PAT_ADDRESS") or input("请输入地址 (可选): ").strip()
    patient_info = {
        "patName": pat_name,
        "sex": pat_sex,
        "birthday": pat_birthday,
        "idNumber": pat_id,
        "address": pat_address,
        "allergies": "暂无过敏史"
    }

    bot = RegistrationBot(BASE_URL, token)
    try:
        bot.run(clinic_id, user_id, member_id, patient_info)
    except Exception as e:
        print(f"发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()