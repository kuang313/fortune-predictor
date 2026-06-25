import sys
import os
import locale
import random
import requests
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from config import Config

# ---------- 强制设置 UTF-8 编码（解决 Latin-1 编码错误） ----------
try:
    locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
except:
    pass
sys.stdout.reconfigure(encoding='utf-8')

# ---------- 初始化 Flask ----------
app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config.from_object(Config)

# ---------- 天干地支定义（原有） ----------
TIAN_GAN = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸']
DI_ZHI = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥']
SHI_CHEN = ['子时(23-1)', '丑时(1-3)', '寅时(3-5)', '卯时(5-7)', '辰时(7-9)',
            '巳时(9-11)', '午时(11-13)', '未时(13-15)', '申时(15-17)',
            '酉时(17-19)', '戌时(19-21)', '亥时(21-23)']

# ---------- 原有：八字排盘（纯公式） ----------
def get_bazi(year, month, day, hour_index):
    """根据公历日期和时辰索引计算八字"""
    # 年柱
    year_gan = TIAN_GAN[(year - 4) % 10]
    year_zhi = DI_ZHI[(year - 4) % 12]
    # 月柱（简化）
    month_gan = TIAN_GAN[(year * 2 + month + 1) % 10]
    month_zhi = DI_ZHI[(month + 1) % 12]
    # 日柱（基准1900-01-01甲子日）
    base_year = 1900
    days = 0
    for y in range(base_year, year):
        days += 366 if (y % 4 == 0 and y % 100 != 0) or (y % 400 == 0) else 365
    month_days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    for m in range(1, month):
        days += month_days[m-1]
        if m == 2 and ((year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)):
            days += 1
    days += day - 1
    day_gan = TIAN_GAN[days % 10]
    day_zhi = DI_ZHI[days % 12]
    # 时柱（五鼠遁）
    hour_gan = TIAN_GAN[((TIAN_GAN.index(day_gan)) % 5 * 2 + hour_index) % 10]
    hour_zhi = DI_ZHI[hour_index]
    return {
        'year': f'{year_gan}{year_zhi}',
        'month': f'{month_gan}{month_zhi}',
        'day': f'{day_gan}{day_zhi}',
        'hour': f'{hour_gan}{hour_zhi}'
    }

# ---------- 原有：AI运势解读（修复编码） ----------
def get_ai_fortune(bazi, api_key, model='glm-4-flash'):
    """调用智谱 GLM-4-Flash 生成运势解读（已修复编码）"""
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
                "Content-Type": "application/json; charset=utf-8"   # ✅ 修复：指定 UTF-8
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

# ---------- 原有路由 ----------
@app.route('/')
def index():
    return render_template('index.html', shichen=SHI_CHEN, enumerate=enumerate)

@app.route('/admin')
def admin():
    api_key = app.config.get('GLM_API_KEY', '')
    masked = api_key[:10] + '***' if api_key else '未配置'
    return render_template('admin.html', api_key=masked)

@app.route('/api/predict', methods=['POST'])
def predict():
    """原有预测接口（不变）"""
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
    """原有配置接口（不变）"""
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

# ---------- 新增：V1.0 MVP 娱乐功能 ----------
# 塔罗牌数据
TAROT_CARDS = [
    {"name": "愚者", "meaning": "新的开始，冒险，天真，自由", "positive": True},
    {"name": "魔术师", "meaning": "创造力，自信，掌握资源", "positive": True},
    {"name": "女祭司", "meaning": "直觉，潜意识，神秘", "positive": True},
    {"name": "皇后", "meaning": "丰收，母性，自然", "positive": True},
    {"name": "皇帝", "meaning": "权威，稳定，保护", "positive": True},
    {"name": "教皇", "meaning": "传统，信仰，教导", "positive": True},
    {"name": "恋人", "meaning": "爱情，选择，结合", "positive": True},
    {"name": "战车", "meaning": "胜利，意志力，自律", "positive": True},
    {"name": "力量", "meaning": "勇气，耐心，内在力量", "positive": True},
    {"name": "隐士", "meaning": "内省，智慧，寻求真理", "positive": True},
    {"name": "命运之轮", "meaning": "命运，变化，机遇", "positive": True},
    {"name": "正义", "meaning": "公正，因果，平衡", "positive": True},
    {"name": "倒吊人", "meaning": "牺牲，换个角度，等待", "positive": False},
    {"name": "死神", "meaning": "结束，转变，新开始", "positive": False},
    {"name": "节制", "meaning": "平衡，调节，融合", "positive": True},
    {"name": "恶魔", "meaning": "束缚，物质，欲望", "positive": False},
    {"name": "高塔", "meaning": "突变，毁灭，觉醒", "positive": False},
    {"name": "星星", "meaning": "希望，灵感，宁静", "positive": True},
    {"name": "月亮", "meaning": "潜意识，幻想，不安", "positive": False},
    {"name": "太阳", "meaning": "成功，活力，喜悦", "positive": True},
    {"name": "审判", "meaning": "重生，觉醒，宽恕", "positive": True},
    {"name": "世界", "meaning": "完成，圆满，成就", "positive": True},
]

# 趣味测试题库
QUIZZES = [{
    "id": 1,
    "title": "你是哪种命理人格？",
    "questions": [
        {
            "q": "你更喜欢哪种生活方式？",
            "options": [
                {"text": "按计划行事", "score": "土"},
                {"text": "随性而为", "score": "水"},
                {"text": "追求新鲜刺激", "score": "火"},
                {"text": "稳中求变", "score": "木"}
            ]
        },
        {
            "q": "遇到困难时你通常会？",
            "options": [
                {"text": "冷静分析", "score": "金"},
                {"text": "寻求他人帮助", "score": "水"},
                {"text": "迎难而上", "score": "火"},
                {"text": "换个思路解决", "score": "木"}
            ]
        },
        {
            "q": "你的社交风格是？",
            "options": [
                {"text": "善于倾听", "score": "土"},
                {"text": "热情开朗", "score": "火"},
                {"text": "温和体贴", "score": "水"},
                {"text": "幽默风趣", "score": "木"}
            ]
        }
    ],
    "result_map": {
        "金": {"type": "金型人格", "desc": "你意志坚定，目标明确，是天生的领导者。做事果断，讲究效率，但有时过于严肃。"},
        "木": {"type": "木型人格", "desc": "你充满创意和活力，善于沟通，适应力强。你像大树一样不断成长，给人带来生机。"},
        "水": {"type": "水型人格", "desc": "你智慧深邃，情感丰富，善于共情。你像水一样温柔而坚韧，包容万物。"},
        "火": {"type": "火型人格", "desc": "你热情似火，充满激情和动力。你善于点燃他人，但也要注意控制自己的急躁。"},
        "土": {"type": "土型人格", "desc": "你稳重可靠，脚踏实地，是团队的中流砥柱。你给人安全感，但偶尔也需要尝试新鲜事物。"}
    }
}]

@app.route('/api/daily', methods=['POST'])
def daily_api():
    """新增：每日运势（基于出生年月日）"""
    data = request.get_json()
    if not data or 'year' not in data:
        return jsonify({'success': False, 'error': '缺少出生年份'}), 400

    year = int(data['year'])
    month = int(data.get('month', 1))
    day = int(data.get('day', 1))
    seed = year * 10000 + month * 100 + day
    random.seed(seed + datetime.now().toordinal())

    keywords = ['突破', '沉淀', '邂逅', '奋进', '平衡', '创造', '守护', '绽放', '启程', '收获']
    colors = ['翡翠绿', '宝石蓝', '珊瑚红', '香槟金', '薰衣草紫', '珍珠白', '琥珀橙']
    items = ['白水晶手链', '黑曜石挂坠', '粉晶手串', '紫水晶耳环', '绿松石戒指', '红玛瑙手镯']
    advices = ['今天适合主动出击，把握机会。', '建议多与人交流，会有意外收获。', '保持平和心态，一切自有安排。', '适合学习新事物，提升自己。', '注意身体健康，适当运动。']

    return jsonify({
        'success': True,
        'daily': {
            'score': random.randint(60, 98),
            'keyword': random.choice(keywords),
            'color': random.choice(colors),
            'lucky_num': random.randint(1, 9),
            'item': random.choice(items),
            'advice': random.choice(advices),
            'date': datetime.now().strftime('%Y-%m-%d')
        }
    })

@app.route('/api/tarot', methods=['GET'])
def tarot_api():
    """新增：随机塔罗牌"""
    card = random.choice(TAROT_CARDS)
    reversed_pos = random.choice([True, False]) if not card['positive'] else False
    position = '逆位' if reversed_pos else '正位'
    meaning = card['meaning']
    if reversed_pos:
        meaning = meaning.replace('积极', '需反思').replace('好运', '挑战')
    return jsonify({
        'success': True,
        'card': {
            'name': card['name'],
            'position': position,
            'meaning': meaning
        }
    })

@app.route('/api/quiz', methods=['GET'])
def quiz_list():
    """新增：获取趣味测试列表"""
    return jsonify({'success': True, 'quizzes': QUIZZES})

@app.route('/api/quiz/submit', methods=['POST'])
def quiz_submit():
    """新增：提交测试答案"""
    data = request.get_json()
    quiz_id = data.get('quiz_id')
    answers = data.get('answers', [])
    if not quiz_id or not answers:
        return jsonify({'success': False, 'error': '参数错误'}), 400

    score_count = {}
    for ans in answers:
        score_count[ans] = score_count.get(ans, 0) + 1
    if not score_count:
        return jsonify({'success': False, 'error': '无有效答案'}), 400
    max_score = max(score_count, key=score_count.get)
    result = QUIZZES[0]['result_map'].get(max_score, {'type': '未知', 'desc': '你是一个独特的存在。'})
    return jsonify({
        'success': True,
        'result': result,
        'detail': f'你的命理人格是：{result["type"]}'
    })

@app.route('/api/health', methods=['GET'])
def health():
    """健康检查（新增）"""
    return jsonify({
        'status': 'ok',
        'message': '命理镜 API 运行中',
        'ai_enabled': bool(app.config.get('GLM_API_KEY'))
    })

# ---------- 启动入口 ----------
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)