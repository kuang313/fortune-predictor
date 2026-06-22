from flask import Flask, render_template, request, jsonify
from datetime import datetime
import requests
import os
from config import Config

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config.from_object(Config)

# 天干地支
TIAN_GAN = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸']
DI_ZHI = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥']
SHI_CHEN = ['子时(23-1)', '丑时(1-3)', '寅时(3-5)', '卯时(5-7)', '辰时(7-9)',
            '巳时(9-11)', '午时(11-13)', '未时(13-15)', '申时(15-17)',
            '酉时(17-19)', '戌时(19-21)', '亥时(21-23)']

def get_bazi(year, month, day, hour_index):
    """
    根据公历日期和时辰索引计算八字（纯公式，无外部依赖）
    hour_index: 0~11 对应子时到亥时
    """
    # 年柱（以立春为界，此处简化按农历年起始，实际应以立春为准，但娱乐工具可用此近似）
    year_gan = TIAN_GAN[(year - 4) % 10]
    year_zhi = DI_ZHI[(year - 4) % 12]

    # 月柱（以节气为界，此处简化按农历月，实际需节气，娱乐工具可接受）
    month_gan = TIAN_GAN[(year * 2 + month + 1) % 10]
    month_zhi = DI_ZHI[(month + 1) % 12]

    # 日柱（使用基准日算法：1900-01-01 为甲子日，此处计算偏移）
    # 计算从1900-01-01到目标日期的天数
    base_year = 1900
    base_month = 1
    base_day = 1
    # 累计年份天数
    days = 0
    for y in range(base_year, year):
        days += 366 if (y % 4 == 0 and y % 100 != 0) or (y % 400 == 0) else 365
    # 累计月份天数
    month_days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    for m in range(1, month):
        days += month_days[m-1]
        if m == 2 and ((year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)):
            days += 1  # 闰年二月多一天
    days += day - 1  # 减去1，因为从0开始

    # 1900-01-01 是甲子日（天干索引0，地支索引0）
    # 日干 = (days + 0) % 10，日支 = (days + 0) % 12
    day_gan = TIAN_GAN[days % 10]
    day_zhi = DI_ZHI[days % 12]

    # 时柱（根据日干和时辰地支推算时干）
    # 五鼠遁：甲己还加甲，乙庚丙作初，丙辛从戊起，丁壬庚子居，戊癸何方发，壬子是真途
    # 日干索引：0甲,1乙,2丙,3丁,4戊,5己,6庚,7辛,8壬,9癸
    # 时干 = (日干索引 % 5) * 2 + 时支索引（子时为0）
    hour_gan = TIAN_GAN[((TIAN_GAN.index(day_gan)) % 5 * 2 + hour_index) % 10]
    hour_zhi = DI_ZHI[hour_index]

    return {
        'year': f'{year_gan}{year_zhi}',
        'month': f'{month_gan}{month_zhi}',
        'day': f'{day_gan}{day_zhi}',
        'hour': f'{hour_gan}{hour_zhi}'
    }

def get_ai_fortune(bazi, api_key, model='glm-4-flash'):
    """调用智谱 GLM-4-Flash 生成运势解读"""
    bazi_str = f"{bazi['year']} {bazi['month']} {bazi['day']} {bazi['hour']}"
    prompt = f"""你是一位资深命理师。请根据用户的八字命盘，提供一份详细的运势分析报告。

用户八字：{bazi_str}

请从以下维度分析（总字数300-400字）：
1. 性格特质：这个命主的天性、优势与短板
2. 事业发展：适合的方向、近期机遇
3. 感情运程：当下的感情状态与建议
4. 财运走势：近期财务趋势与建议
5. 健康提示：需要注意的方面

语气要求：温和亲切、通俗易懂，不要过于玄学晦涩。最后用一个成语总结今日开运提示。"""

    try:
        response = requests.post(
            "https://open.bigmodel.cn/api/paas/v4/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "你是一位专业且亲和的命理咨询师。"},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.8,
                "max_tokens": 800,
                "stream": False
            },
            timeout=30
        )
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content']
        else:
            return f"API调用失败：{response.status_code}，请检查API Key是否正确"
    except Exception as e:
        return f"请求异常：{str(e)}"

@app.route('/')
def index():
    return render_template('index.html', shichen=SHI_CHEN)

@app.route('/admin')
def admin():
    api_key = app.config.get('GLM_API_KEY', '')
    masked = api_key[:10] + '***' if api_key else '未配置'
    return render_template('admin.html', api_key=masked)

@app.route('/api/predict', methods=['POST'])
def predict():
    try:
        data = request.json
        birth_date = datetime.strptime(data['birthday'], '%Y-%m-%d')
        hour_idx = int(data['hour'])
        api_key = app.config.get('GLM_API_KEY')
        if not api_key:
            return jsonify({'status': 'error', 'message': '请先联系管理员配置API Key'})
        bazi = get_bazi(birth_date.year, birth_date.month, birth_date.day, hour_idx)
        bazi_str = f"{bazi['year']} {bazi['month']} {bazi['day']} {bazi['hour']}"
        fortune_text = get_ai_fortune(bazi, api_key, app.config.get('GLM_MODEL', 'glm-4-flash'))
        return jsonify({
            'status': 'success',
            'data': {
                'bazi': bazi_str,
                'fortune': fortune_text
            }
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/config', methods=['POST'])
def update_config():
    try:
        data = request.json
        new_key = data.get('api_key', '').strip()
        model = data.get('model', 'glm-4-flash')
        if not new_key:
            return jsonify({'status': 'error', 'message': 'API Key不能为空'})
        os.environ['GLM_API_KEY'] = new_key
        os.environ['GLM_MODEL'] = model
        app.config['GLM_API_KEY'] = new_key
        app.config['GLM_MODEL'] = model
        return jsonify({'status': 'success', 'message': '配置已更新'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)