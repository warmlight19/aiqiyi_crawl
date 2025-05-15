from flask import Flask, render_template, redirect, jsonify, request, send_file
from flask_socketio import SocketIO
import os
import json
import requests
import re
from io import BytesIO
import pandas as pd
from datetime import datetime
from scrape_route import init_scraping_routes

from scraper import get_recommended_videos, save_recommendations_to_csv
import traceback

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['SECRET_KEY'] = os.urandom(24)
socketio = SocketIO(app, cors_allowed_origins="*")

# 初始化爬取相关的Socket.IO事件处理
init_scraping_routes(socketio)

def clean_rating(rating):
    """处理评分数据"""
    if pd.isna(rating) or str(rating).strip() in ['无', '暂无推荐分', '敬请期待']:
        return None
    
    # 处理包含换行符的情况
    rating = str(rating).strip().replace('\n', ' ').replace('\r', '')
    
    # 提取数字评分
    match = re.search(r'(\d+\.?\d*)', rating)
    if match:
        return float(match.group(1))
    
    return None

# 首页路由
@app.route('/')
def index():
    return render_template('index.html')

# 数据爬取页路由
@app.route('/scrape')
def scrape():
    return render_template('scrape.html')

# 数据展示页路由
@app.route('/display')
def display():
    return render_template('display.html')

# API路由
@app.route('/api/get_data_files')
def get_data_files():
    data_dir = os.path.join('data', 'hotdata')
    files = []
    
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        return jsonify([])
    
    try:
        for f in os.listdir(data_dir):
            if f.startswith('iqiyi_') and f.endswith('.csv'):
                try:
                    timestamp_str = f[6:-4]
                    dt = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                    
                    files.append({
                        'filename': f,
                        'full_path': os.path.join('hotdata', f),
                        'display_name': dt.strftime("%Y-%m-%d %H:%M:%S"),
                        'timestamp': timestamp_str
                    })
                except ValueError as e:
                    print(f"跳过文件 {f}，时间格式错误: {str(e)}")
                    continue
        
        files.sort(key=lambda x: x['timestamp'], reverse=True)
        return jsonify(files)
    
    except Exception as e:
        return jsonify({'error': f"获取文件列表出错: {str(e)}"}), 500

@app.route('/api/get_video_list')
def get_video_list():
    filename = request.args.get('file')
    if not filename:
        return jsonify({'error': '未指定文件'}), 400
    
    try:
        filepath = os.path.join('data', filename)
        if not os.path.exists(filepath):
            return jsonify({'error': f'文件不存在: {filename}'}), 404
        
        df = pd.read_csv(filepath, encoding='utf-8-sig')
        
        # 根据实际CSV字段调整
        required_columns = ['name', 'link', 'rating_count', 'description', 'cast', 'comments']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            return jsonify({
                'error': f'CSV文件缺少必要列: {", ".join(missing_columns)}',
                'available_columns': list(df.columns)
            }), 400
        
        # 处理视频数据
        videos = []
        for _, row in df.iterrows():
            # 处理评分人数
            rating_count = row.get('rating_count', '暂无评价')
            if isinstance(rating_count, str):
                # 提取数字
                match = re.search(r'(\d+(\.\d+)?)', rating_count)
                if match:
                    rating_count = match.group(1) + '人评价'
                else:
                    rating_count = '暂无评价'
            
            video = {
                'name': row['name'],
                'link': row['link'],
                'rating_count': rating_count,
                'description': row.get('description', '暂无描述'),
                'cast': row.get('cast', '未知')
            }
            videos.append(video)
        
        # 从文件名解析时间
        basename = os.path.basename(filename)
        timestamp_str = basename[6:-4]
        crawl_time = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
        
        return jsonify({
            'videos': videos,
            'count': len(df),
            'crawl_time': crawl_time
        })
        
    except Exception as e:
        return jsonify({'error': f"读取文件失败: {str(e)}"}), 500

@app.route('/api/get_video_details')
def get_video_details():
    filename = request.args.get('file')
    video_name = request.args.get('name')
    
    if not filename or not video_name:
        return jsonify({'error': '缺少参数'}), 400
    
    try:
        filepath = os.path.join('data', filename)
        df = pd.read_csv(filepath, encoding='utf-8-sig')
        
        video_data = df[df['name'] == video_name]
        if video_data.empty:
            return jsonify({'error': '未找到指定视频'}), 404
            
        video_data = video_data.iloc[0].to_dict()
        
        # 处理评论数据
        comments = []
        if 'comments' in video_data and pd.notna(video_data['comments']):
            try:
                # 处理评论JSON字符串
                comments_str = video_data['comments'].replace("'", '"')  # 替换单引号为双引号
                comments = json.loads(comments_str)
                
                # 格式化评论数据
                formatted_comments = []
                for comment in comments:
                    formatted_comments.append({
                        'user_name': comment.get('nickname', '匿名用户'),
                        'user_id': comment.get('user_id', '0'),
                        'content': comment.get('comment_content', ''),
                        'time': comment.get('comment_time', ''),
                        'likes': int(comment.get('like_count', 0)),
                        'avatar_url': comment.get('avatar_url', '')
                    })
                comments = formatted_comments
            except (json.JSONDecodeError, AttributeError) as e:
                print(f"解析评论数据出错: {str(e)}")
                comments = []
        
        # 返回格式化后的视频详情
        return jsonify({
            'name': video_data.get('name', ''),
            'link': video_data.get('link', '#'),
            'rating_count': video_data.get('rating_count', 0),
            'rating': video_data.get('rating', '暂无评分'),
            'description': video_data.get('description', '暂无描述'),
            'cast': video_data.get('cast', '未知'),
            'poster_url': video_data.get('poster_url', ''),
            'comments': comments
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/get_scrape_history')
def get_scrape_history():
    try:
        files = []
        for f in os.listdir('data'):
            if f.endswith('.csv'):
                timestamp = f.split('_')[1].split('.')[0]
                try:
                    dt = datetime.strptime(timestamp, "%Y%m%d_%H%M%S")
                    display_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                    files.append({
                        'filename': f,
                        'time': display_time
                    })
                except:
                    continue
        
        files.sort(key=lambda x: x['time'], reverse=True)
        return jsonify(files[:5])
    except Exception as e:
        return jsonify([])

@app.route('/proxy_image')
def proxy_image():
    url = request.args.get('url')
    if not url:
        return "缺少URL参数", 400
    
    try:
        import requests
        
        # 创建一个Session对象并配置连接池参数
        session = requests.Session()
        # 增加连接池的最大连接数，默认为10
        session.mount('http://', requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20))
        session.mount('https://', requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20))
        
        # 在需要发送请求的地方使用session而不是requests
        response = session.get(url, stream=True, timeout=10)
        if response.status_code == 200:
            return send_file(
                BytesIO(response.content),
                mimetype=response.headers.get('content-type', 'image/jpeg')
            )
        return "图片获取失败", 404
    except Exception as e:
        print(f"图片代理错误: {str(e)}")
        return "图片加载失败", 500


@app.route('/api/get_recommendations')
def get_recommendations():
    video_name = request.args.get('video_name')
    if not video_name:
        return jsonify({'error': '缺少视频名称参数'}), 400
    
    try:
        # 在recommendations目录下查找对应的推荐文件
        recommendations_dir = os.path.join('data', 'recommendations')
        if not os.path.exists(recommendations_dir):
            return jsonify({'error': '推荐数据目录不存在'}), 404
        
        # 查找最新的推荐文件
        recommendation_files = [f for f in os.listdir(recommendations_dir) if f.startswith(f'{video_name}_')]
        if not recommendation_files:
            return jsonify({'error': '未找到该视频的推荐数据'}), 404
        
        # 按时间戳排序，获取最新的推荐文件
        latest_file = sorted(recommendation_files)[-1]
        filepath = os.path.join(recommendations_dir, latest_file)
        
        # 读取推荐数据
        df = pd.read_csv(filepath, encoding='utf-8-sig')
        
        # 处理推荐视频数据
        recommendations = []
        for _, row in df.iterrows():
            video = {
                'name': row.get('name', '未知'),
                'link': row.get('link', '#'),
                'description': row.get('description', '暂无描述'),
                'rating': row.get('rating', '暂无评分'),
                'rating_count': row.get('rating_count', '0'),
                'poster_url': row.get('poster_url', ''),
                'cast': row.get('cast', ''),
                'comments': row.get('comments', '[]')
            }
            recommendations.append(video)
        
        # 从文件名解析时间
        timestamp_str = latest_file.split('_')[1] + '_' + latest_file.split('_')[2].replace('.csv', '')
        crawl_time = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
        
        return jsonify({
            'video_name': video_name,
            'recommendations': recommendations,
            'count': len(recommendations),
            'crawl_time': crawl_time
        })
        
    except Exception as e:
        return jsonify({'error': f'获取推荐数据失败: {str(e)}'}), 500

# @app.route('/api/get_recommendation_history')
# def get_recommendation_history():
#     try:
#         files = []
#         for f in os.listdir('data'):
#             if f.startswith('recommendations_') and f.endswith('.csv'):
#                 timestamp = f.split('_')[1].split('.')[0]
#                 try:
#                     dt = datetime.strptime(timestamp, "%Y%m%d_%H%M%S")
#                     display_time = dt.strftime("%Y-%m-%d %H:%M:%S")
#                     files.append({
#                         'filename': f,
#                         'time': display_time
#                     })
#                 except:
#                     continue
        
#         files.sort(key=lambda x: x['time'], reverse=True)
#         return jsonify(files[:5])
#     except Exception as e:
#         return jsonify([])









if __name__ == '__main__':
    if not os.path.exists('data'):
        os.makedirs('data')
    socketio.run(app, debug=True, port=5001)