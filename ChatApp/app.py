from flask import Flask, request, redirect, render_template, session, flash, abort, url_for
from datetime import timedelta
import hashlib
import uuid
import re
import os

from models import User, Channel, Message
from util.assets import bundle_css_files


# 定数定義
EMAIL_PATTERN = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
SESSION_DAYS = 30

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', uuid.uuid4().hex)
app.permanent_session_lifetime = timedelta(days=SESSION_DAYS)

# ブラウザに静的ファイル（CSSや画像など）を長くキャッシュさせる設定。
# 開発中は変更がすぐ反映されないことがあるため、コメントアウトするのが無難です。
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 2678400

# 複数のCSSファイルを1つにまとめて圧縮（バンドル）する処理を実行。
bundle_css_files(app)


# ルートページのリダイレクト処理
@app.route('/', methods=['GET'])
def index():
    uid = session.get('uid')
    if uid is None:
        return redirect(url_for('login_view'))
    return redirect(url_for('channels_view'))


# サインアップページの表示
@app.route('/signup', methods=['GET'])
def signup_view():
    return render_template('auth/signup.html')


# サインアップ処理
@app.route('/signup', methods=['POST'])
def signup_process():
    name = request.form.get('name')
    email = request.form.get('email')
    password = request.form.get('password')
    passwordConfirmation = request.form.get('password-confirmation')

    if name == '' or email =='' or password == '' or passwordConfirmation == '':
        flash('空のフォームがあるようです')
    elif password != passwordConfirmation:
        flash('二つのパスワードの値が違っています')
    elif re.match(EMAIL_PATTERN, email) is None:
        flash('正しいメールアドレスの形式ではありません')
    else:
        uid = uuid.uuid4()
        password = hashlib.sha256(password.encode('utf-8')).hexdigest()
        registered_user = User.find_by_email(email)

        if registered_user != None:
            flash('既に登録されているようです')
        else:
            User.create(uid, name, email, password)
            UserId = str(uid)
            session['uid'] = UserId
            return redirect(url_for('channels_view'))
    return redirect(url_for('signup_process'))


# ログインページの表示
@app.route('/login', methods=['GET'])
def login_view():
    return render_template('auth/login.html')


# ログイン処理
@app.route('/login', methods=['POST'])
def login_process():
    email = request.form.get('email')
    password = request.form.get('password')

    if email =='' or password == '':
        flash('空のフォームがあるようです')
    else:
        user = User.find_by_email(email)
        if user is None:
            flash('このユーザーは存在しません')
        else:
            hashPassword = hashlib.sha256(password.encode('utf-8')).hexdigest()
            if hashPassword != user["password"]:
                flash('パスワードが間違っています！')
            else:
                session['uid'] = user["uid"]
                return redirect(url_for('channels_view'))
    return redirect(url_for('login_view'))


# ログアウト
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_view'))


# チャンネル一覧ページの表示
@app.route('/channels', methods=['GET'])
def channels_view():
    uid = session.get('uid')
    if uid is None:
        return redirect(url_for('login_view'))
    else:
        channels = Channel.get_all()
        channels.reverse()
        return render_template('channels.html', channels=channels, uid=uid)


# チャンネルの作成
@app.route('/channels', methods=['POST'])
def create_channel():
    uid = session.get('uid')
    if uid is None:
        return redirect(url_for('login_view'))

    channel_name = request.form.get('channelTitle')
    channel = Channel.find_by_name(channel_name)
    if channel == None:
        channel_description = request.form.get('channelDescription')
        Channel.create(uid, channel_name, channel_description)
        return redirect(url_for('channels_view'))
    else:
        error = '既に同じ名前のチャンネルが存在しています'
        return render_template('error/error.html', error_message=error)


# チャンネルの更新
@app.route('/channels/update/<cid>', methods=['POST'])
def update_channel(cid):
    uid = session.get('uid')
    if uid is None:
        return redirect(url_for('login_view'))

    channel = Channel.find_by_cid(cid)
    if channel is None:
        return redirect(url_for('channels_view'))
    # 作成者以外は編集不可（他人のチャンネルの乗っ取り・改ざんを防ぐ）
    if channel["uid"] != uid:
        flash('チャンネルは作成者のみ編集可能です')
        return redirect(url_for('channels_view'))

    channel_name = request.form.get('channelTitle')
    channel_description = request.form.get('channelDescription')

    Channel.update(channel_name, channel_description, cid)
    return redirect(f'/channels/{cid}/messages')


# チャンネルの削除
@app.route('/channels/delete/<cid>', methods=['POST'])
def delete_channel(cid):
    uid = session.get('uid')
    if uid is None:
        return redirect(url_for('login_view'))

    channel = Channel.find_by_cid(cid)

    if channel is None:
        return redirect(url_for('channels_view'))
    if channel["uid"] != uid:
        flash('チャンネルは作成者のみ削除可能です')
    else:
        Channel.delete(cid)
    return redirect(url_for('channels_view'))


# チャンネル詳細ページの表示（各チャンネル内で、そのチャンネルに属している全メッセージを表示させる）
@app.route('/channels/<cid>/messages', methods=['GET'])
def detail(cid):
    uid = session.get('uid')
    if uid is None:
        return redirect(url_for('login_view'))

    channel = Channel.find_by_cid(cid)
    messages = Message.get_all(cid)

    return render_template('messages.html', messages=messages, channel=channel, uid=uid)


# メッセージの投稿
@app.route('/channels/<cid>/messages', methods=['POST'])
def create_message(cid):
    uid = session.get('uid')
    if uid is None:
        return redirect(url_for('login_view'))

    message = request.form.get('message')

    if message:
        Message.create(uid, cid, message)

    return redirect('/channels/{cid}/messages'.format(cid = cid))


# メッセージの削除
@app.route('/channels/<cid>/messages/<message_id>', methods=['POST'])
def delete_message(cid, message_id):
    uid = session.get('uid')
    if uid is None:
        return redirect(url_for('login_view'))

    message = Message.find_by_id(message_id)
    if message is None:
        return redirect('/channels/{cid}/messages'.format(cid = cid))
    # 投稿者以外は削除不可（他人のメッセージを消せないようにする）
    if message["uid"] != uid:
        flash('メッセージは投稿者のみ削除可能です')
        return redirect('/channels/{cid}/messages'.format(cid = cid))

    Message.delete(message_id)
    return redirect('/channels/{cid}/messages'.format(cid = cid))


@app.errorhandler(404)
def page_not_found(error):
    return render_template('error/404.html'),404


@app.errorhandler(500)
def internal_server_error(error):
    return render_template('error/500.html'),500


if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True)
