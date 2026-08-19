# 预约挂号相关接口文档

> **公共信息**
> 
> - **服务地址**：`gw.cbyzs.com`
>     
> - **协议**：HTTPS（示例中使用 HTTP/2）
>     
> - **公共请求头**（所有接口均需携带）：
>     
>     - `Authorization:eyJhbGciOiJSUzI1NiIsInR5cCIg...`
>         
>     - `Cb-Client: cb-ihospital-wx`
>         
>     - `Cb-Version: cbjy-mini-app@6.1.0`
>         
>     - `Charset: utf-8`
>         
>     - `Referer: https://servicewechat.com/wxcab6b298816d6b65/167/page-frame.html`
>         
>     - `User-Agent: Mozilla/5.0 ...`
>         
> - **响应统一格式**：
>     
>     - `code`: 0 表示成功，其他为错误码
>         
>     - `msg`: 提示信息
>         
>     - `data`: 具体数据（类型不定）
>         
>     - `success`: true/false
>         

---

## 1. 按天显示是否有号

**说明**：查询指定日期范围内，某诊所每天是否有剩余号源（`hasSource`：1=有号，0=无号）。

### 请求信息

- **Method**：`GET`
    
- **Path**：`/cbyzs-scheduler/opsource/v1/getClinicSourceWeek`
    
- **Query 参数**：
    

|参数名|类型|必填|说明|
|---|---|---|---|
|`clinicId`|string|✅|诊所ID（示例：`1641457759539081218`）|
|`sdate`|string|✅|开始日期，格式 `YYYY-MM-DD`|
|`edate`|string|✅|结束日期，格式 `YYYY-MM-DD`|

### 请求示例

```http
GET /cbyzs-scheduler/opsource/v1/getClinicSourceWeek?clinicId=1641457759539081218&sdate=2026-08-18&edate=2026-08-25 HTTP/2
Host: gw.cbyzs.com
Authorization: <token>
Cb-Client: cb-ihospital-wx
```

### 响应示例（成功）

```json
{
  "code": 0,
  "msg": "操作成功",
  "data": [
    {
      "clinicId": "1641457759539081218",
      "date": "2026-08-18",
      "day": "18",
      "week": "周二",
      "hasSource": 0
    },
    {
      "clinicId": "1641457759539081218",
      "date": "2026-08-19",
      "day": "19",
      "week": "周三",
      "hasSource": 1
    }
    // ... 更多日期
  ],
  "success": true
}
```

### 响应字段说明

|字段|说明|
|---|---|
|`data[].date`|日期|
|`data[].week`|星期|
|`data[].hasSource`|是否有号（0=无，1=有）|

---

## 2. 获取诊所医生列表

**说明**：根据诊所ID获取该诊所下的医生信息，包括医生简介、排班日期、上/下午号源数量等。

### 请求信息

- **Method**：`GET`
    
- **Path**：`/cbyzs-scheduler/v1/appointRegister/getDocListByClinicIdV2`
    
- **Query 参数**：
    

|参数名|类型|必填|说明|
|---|---|---|---|
|`clinicId`|string|✅|诊所ID|
|`current`|int|❌|页码，默认为1|
|`size`|int|❌|每页条数，默认为100|
|`searchDate`|string|❌|筛选日期，空则返回所有排班|

### 请求示例

```http
GET /cbyzs-scheduler/v1/appointRegister/getDocListByClinicIdV2?clinicId=1641457759539081218&current=1&size=100&searchDate= HTTP/2
Host: gw.cbyzs.com
Authorization: <token>
Cb-Client: cb-ihospital-wx
```

### 响应示例（成功，已精简部分字段）

```json
{
  "code": 0,
  "msg": "操作成功",
  "data": {
    "records": [
      {
        "docId": "1641457760482799618",
        "docName": "郭彦丽",
        "title": "主治医师",
        "deptName": "全科门诊",
        "clinicName": "南开河郭彦丽卫生室",
        "clinicAddress": "河北省邯郸市磁县磁县磁州镇南开河村综治中心(泰山路南)",
        "registrationStatus": 1,
        "sourceDayList": [
          {
            "date": "2026-08-19",
            "desc": "周三",
            "type": 1,
            "visitNumber": 19,
            "config": "08月19日07:00放号"
          },
          {
            "date": "2026-08-19",
            "desc": "周三",
            "type": 2,
            "visitNumber": 35,
            "config": "08月19日07:00放号"
          }
          // ... 更多日期
        ],
        "bankingHours": [
          { "startTime": "08:00", "endTime": "12:00" },
          { "startTime": "13:00", "endTime": "17:00" }
        ]
      }
    ],
    "total": 1,
    "pages": 1
  },
  "success": true
}
```

### 响应关键字段说明

|字段|说明|
|---|---|
|`records[].docId`|医生ID|
|`records[].docName`|医生姓名|
|`records[].title`|职称|
|`records[].sourceDayList[].type`|时段：1=上午，2=下午|
|`records[].sourceDayList[].visitNumber`|该时段号源总数|
|`records[].sourceDayList[].config`|放号时间说明|
|`records[].bankingHours`|诊所营业时间段|

---

## 3. 获取具体号源列表（sourceIds）

**说明**：根据医生、日期和时段（上午/下午），获取该时段下每个具体号源的 ID、开始结束时间等信息，用于后续锁定。

### 请求信息

- **Method**：`GET`
    
- **Path**：`/cbyzs-scheduler/opsource/v1/getDocNoonSource`
    
- **Query 参数**：
    

|参数名|类型|必填|说明|
|---|---|---|---|
|`date`|string|✅|日期，格式 `YYYY-MM-DD`|
|`docId`|string|✅|医生ID|
|`type`|int|✅|时段：1=上午，2=下午|

### 请求示例

```http
GET /cbyzs-scheduler/opsource/v1/getDocNoonSource?date=2026-08-19&docId=1641457760482799618&type=2 HTTP/2
Host: gw.cbyzs.com
Authorization: <token>
Cb-Client: cb-ihospital-wx
```

### 响应示例（成功，已精简）

```json
{
  "code": 0,
  "msg": "操作成功",
  "data": [
    {
      "sourceId": "2087333320952561670",
      "stratTime": "12:00",
      "endTime": "12:00",
      "total": 1,
      "regTimeMode": 1,
      "sourceIds": ["2087333320952561670"]
    },
    {
      "sourceId": "2087333320952561671",
      "stratTime": "13:07",
      "endTime": "13:14",
      "total": 1,
      "regTimeMode": 1,
      "sourceIds": ["2087333320952561671"]
    }
    // ... 更多号源
  ],
  "success": true
}
```

### 响应字段说明

|字段|说明|
|---|---|
|`data[].sourceId`|当前号源ID（用于锁定）|
|`data[].stratTime`|号源开始时间|
|`data[].endTime`|号源结束时间|
|`data[].total`|该号源可预约人数（通常为1）|

---

## 4. 检查是否有已锁定的号源

**说明**：在尝试锁定新号源前，检查当前用户是否已有未过期的锁定号源。若有，则不能再锁定其他号源（需先处理或等待过期）。

### 请求信息

- **Method**：`GET`
    
- **Path**：`/cbyzs-mobile-doctor-backend/hospitalOrder/scheduleLockCheck`
    
- **Query 参数**：
    

|参数名|类型|必填|说明|
|---|---|---|---|
|`userId`|string|✅|用户ID|

### 请求示例

```http
GET /cbyzs-mobile-doctor-backend/hospitalOrder/scheduleLockCheck?userId=2088462718583033858 HTTP/2
Host: gw.cbyzs.com
Authorization: <token>
Cb-Client: cb-ihospital-wx
```

### 响应示例（有锁定时）

```json
{
  "code": 0,
  "msg": "操作成功",
  "data": {
    "sourceId": "2087333320948367378",
    "doctorId": "1641457760482799618",
    "expireTime": "2026-08-18 22:22:57",
    "dayDate": "2026-08-19",
    "startTime": "09:50",
    "endTime": "09:57",
    "week": "周三"
  },
  "success": true
}
```

> **注意**：若 `data` 为空或 `null`，表示当前无锁定号源。

### 响应字段说明

|字段|说明|
|---|---|
|`data.sourceId`|已锁定的号源ID|
|`data.doctorId`|医生ID|
|`data.expireTime`|锁定过期时间，超时自动释放|
|`data.dayDate`|就诊日期|

---

## 5. 锁定号源

**说明**：用户选择某个具体号源后，调用此接口进行临时锁定（通常锁定时间为几分钟），锁定成功后需在过期前完成下单。

### 请求信息

- **Method**：`POST`
    
- **Path**：`/cbyzs-mobile-doctor-backend/hospitalOrder/scheduleLock`
    
- **Headers**：`Content-Type: application/json`
    
- **Body 参数**（JSON）：
    

|参数名|类型|必填|说明|
|---|---|---|---|
|`userId`|string|✅|用户ID|
|`sourceId`|string|✅|号源ID（来自接口3）|

### 请求示例

```json
{
  "userId": "2088462718583033858",
  "sourceId": "2087333320948367378"
}
```

### 响应示例（成功）

```json
{
  "code": 0,
  "msg": "操作成功",
  "data": {
    "sourceId": "2087333320948367378",
    "doctorId": "1641457760482799618",
    "expireTime": "2026-08-18 22:22:56",
    "dayDate": null,
    "startTime": null,
    "endTime": null,
    "week": null
  },
  "success": true
}
```

### 响应字段说明

|字段|说明|
|---|---|
|`data.sourceId`|锁定的号源ID|
|`data.doctorId`|医生ID|
|`data.expireTime`|锁定失效时间，需在此前提交订单|

---

## 6. 添加预约订单

**说明**：锁定号源后，调用此接口提交正式预约订单，完成挂号。

### 请求信息

- **Method**：`POST`
    
- **Path**：`/cbyzs-mobile-doctor-backend/hospitalOrder/addVisitOrder`
    
- **Headers**：`Content-Type: application/json`
    
- **Body 参数**（JSON，部分字段可空）：
    

|参数名|类型|必填|说明|
|---|---|---|---|
|`userId`|string|✅|用户ID|
|`patName`|string|✅|患者姓名|
|`patSex`|string|✅|患者性别（"男"/"女"）|
|`birthday`|string|✅|出生日期，格式 `YYYY-MM-DD`|
|`clinicId`|string|✅|诊所ID|
|`deptId`|string|✅|科室ID|
|`deptName`|string|✅|科室名称|
|`docId`|string|✅|医生ID|
|`docName`|string|✅|医生姓名|
|`sourceId`|string|✅|锁定的号源ID|
|`memberId`|string|✅|会员/就诊人ID|
|`allergies`|string|❌|过敏史，默认"暂无过敏史"|
|`regFee`|string|❌|挂号费，默认"0"|
|其他|-|❌|地址、身份证、省市等可留空|

### 请求示例

```json
{
  "userId": "2088462718583033858",
  "patName": "王星星",
  "patSex": "男",
  "birthday": "2006-12-01",
  "clinicId": "1641457759539081218",
  "deptId": "4711879525904943060",
  "deptName": "全科门诊",
  "docId": "1641457760482799618",
  "docName": "郭彦丽",
  "sourceId": "2087333320948367378",
  "memberId": "2088600096131895298",
  "allergies": "暂无过敏史",
  "regFee": "0",
  "filelist": [],
  "symptoms": "",
  "temperature": ""
}
```

### 响应示例（成功）

```json
{
  "code": 0,
  "msg": "操作成功",
  "data": {
    "id": "2089719025803501569",
    "orderNumber": "YY260818001884",
    "employeeName": "郭彦丽",
    "orderStatus": "0501",
    "amount": 0,
    "createTime": "2026-08-18 22:20:14"
  },
  "success": true
}
```

### 响应关键字段说明

|字段|说明|
|---|---|
|`data.id`|订单ID|
|`data.orderNumber`|订单编号|
|`data.orderStatus`|订单状态（"0501" 表示待就诊等）|
|`data.amount`|支付金额（0表示免费）|