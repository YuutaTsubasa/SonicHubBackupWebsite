#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SonicHub Forum SQL to Static Website Converter

This script converts the SonicHub forum database (sonichub_forum.sql) 
into a static HTML website.
"""

import re
import os
import json
import html
from datetime import datetime
from collections import defaultdict, OrderedDict
from pathlib import Path
import shutil

class SonicHubConverter:
    def __init__(self, sql_file, output_dir="website", attachments_dir="attachments"):
        self.sql_file = sql_file
        self.output_dir = output_dir
        self.attachments_dir = attachments_dir
        
        # Data structures
        self.forums = {}
        self.posts = []
        self.attachments = {}
        self.threads = defaultdict(list)  # tid -> list of posts
        
    def parse_sql_file(self):
        """Parse the SQL file and extract forum data"""
        print("正在解析 SQL 檔案...")
        
        with open(self.sql_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Extract forums
        self._extract_forums(content)
        
        # Extract posts
        self._extract_posts(content)
        
        # Extract attachments
        self._extract_attachments(content)
        
        # Organize posts into threads
        self._organize_threads()
        
        print(f"解析完成: {len(self.forums)} 個版塊, {len(self.posts)} 篇文章, {len(self.attachments)} 個附件")
    
    def _extract_forums(self, content):
        """Extract forum data from SQL"""
        # Find the INSERT statement for cdb_forums
        forum_pattern = r"INSERT INTO `cdb_forums`.*?VALUES\s*(.*?);"
        forum_match = re.search(forum_pattern, content, re.DOTALL)
        
        if forum_match:
            values_text = forum_match.group(1)
            # Parse individual forum records
            forum_records = self._parse_sql_values(values_text)
            
            for record in forum_records:
                if len(record) >= 4:
                    fid = int(record[0]) if record[0].isdigit() else 0
                    fup = int(record[1]) if record[1].isdigit() else 0
                    forum_type = record[2].strip("'\"")
                    name = record[3].strip("'\"").replace('\\r\\n', '').replace('\\n', '')
                    
                    self.forums[fid] = {
                        'fid': fid,
                        'fup': fup,
                        'type': forum_type,
                        'name': name,
                        'posts': [],
                        'threads': []
                    }
    
    def _extract_posts(self, content):
        """Extract post data from SQL"""
        # Find the INSERT statements for cdb_posts
        post_pattern = r"INSERT INTO `cdb_posts`.*?VALUES\s*(.*?);"
        
        for match in re.finditer(post_pattern, content, re.DOTALL):
            values_text = match.group(1)
            post_records = self._parse_sql_values(values_text)
            
            for record in post_records:
                if len(record) >= 9:
                    try:
                        post = {
                            'pid': int(record[0]),
                            'fid': int(record[1]),
                            'tid': int(record[2]),
                            'first': int(record[3]),
                            'author': record[4].strip("'\""),
                            'authorid': int(record[5]),
                            'subject': record[6].strip("'\"").replace('\\r\\n', '\n').replace('\\n', '\n'),
                            'dateline': int(record[7]),
                            'message': record[8].strip("'\"").replace('\\r\\n', '\n').replace('\\n', '\n')
                        }
                        self.posts.append(post)
                        
                        # Add to forum's posts
                        if post['fid'] in self.forums:
                            self.forums[post['fid']]['posts'].append(post)
                            
                    except (ValueError, IndexError) as e:
                        print(f"警告: 無法解析文章記錄: {e}")
                        continue
    
    def _extract_attachments(self, content):
        """Extract attachment data from SQL"""
        attachment_pattern = r"INSERT INTO `cdb_attachments`.*?VALUES\s*(.*?);"
        
        for match in re.finditer(attachment_pattern, content, re.DOTALL):
            values_text = match.group(1)
            attachment_records = self._parse_sql_values(values_text)
            
            for record in attachment_records:
                if len(record) >= 11:
                    try:
                        aid = int(record[0])
                        attachment = {
                            'aid': aid,
                            'tid': int(record[1]),
                            'pid': int(record[2]),
                            'filename': record[6].strip("'\""),
                            'attachment': record[10].strip("'\""),  # File path
                            'isimage': int(record[12]) if len(record) > 12 else 0
                        }
                        self.attachments[aid] = attachment
                    except (ValueError, IndexError) as e:
                        print(f"警告: 無法解析附件記錄: {e}")
                        continue
    
    def _parse_sql_values(self, values_text):
        """Parse SQL VALUES clause into individual records"""
        # Simple parser for SQL VALUES - handles basic cases
        records = []
        current_record = []
        current_value = ""
        in_quotes = False
        quote_char = None
        i = 0
        
        while i < len(values_text):
            char = values_text[i]
            
            if char in ('"', "'") and not in_quotes:
                in_quotes = True
                quote_char = char
                i += 1
                continue
            elif char == quote_char and in_quotes:
                # Check for escaped quote
                if i + 1 < len(values_text) and values_text[i + 1] == quote_char:
                    current_value += char
                    i += 2
                    continue
                else:
                    in_quotes = False
                    quote_char = None
                    current_record.append(current_value)
                    current_value = ""
                    i += 1
                    continue
            elif in_quotes:
                current_value += char
            elif char == ',':
                if not in_quotes:
                    if not current_value.strip() and len(current_record) == 0:
                        current_record.append("0")  # Default value
                    elif current_value.strip():
                        current_record.append(current_value.strip())
                    current_value = ""
            elif char == '(' and not in_quotes:
                # Start of new record
                current_record = []
                current_value = ""
            elif char == ')' and not in_quotes:
                # End of record
                if current_value.strip():
                    current_record.append(current_value.strip())
                if current_record:
                    records.append(current_record)
                current_record = []
                current_value = ""
            else:
                if not in_quotes and char.isspace():
                    # Skip whitespace outside quotes
                    pass
                elif not in_quotes:
                    current_value += char
                else:
                    current_value += char
            
            i += 1
        
        return records
    
    def _organize_threads(self):
        """Organize posts into threads"""
        for post in self.posts:
            self.threads[post['tid']].append(post)
        
        # Sort posts in each thread by post ID (chronological order)
        for tid in self.threads:
            self.threads[tid].sort(key=lambda p: p['pid'])
    
    def convert_bbcode_to_html(self, text):
        """Convert BBCode to HTML"""
        if not text:
            return ""
        
        # Escape HTML characters first
        text = html.escape(text)
        
        # Convert common BBCode tags
        conversions = [
            # Basic formatting
            (r'\[b\](.*?)\[/b\]', r'<strong>\1</strong>'),
            (r'\[i\](.*?)\[/i\]', r'<em>\1</em>'),
            (r'\[u\](.*?)\[/u\]', r'<u>\1</u>'),
            
            # Colors
            (r'\[color=(.*?)\](.*?)\[/color\]', r'<span style="color: \1">\2</span>'),
            
            # Size
            (r'\[size=(.*?)\](.*?)\[/size\]', r'<span style="font-size: \1px">\2</span>'),
            
            # Links
            (r'\[url=(.*?)\](.*?)\[/url\]', r'<a href="\1" target="_blank">\2</a>'),
            (r'\[url\](.*?)\[/url\]', r'<a href="\1" target="_blank">\1</a>'),
            
            # Images
            (r'\[img\](.*?)\[/img\]', r'<img src="\1" alt="Image" style="max-width: 100%;">'),
            
            # YouTube videos
            (r'\[youtube\](.*?)\[/youtube\]', r'<div class="youtube-container"><iframe width="560" height="315" src="https://www.youtube.com/embed/\1" frameborder="0" allowfullscreen></iframe></div>'),
            
            # Quotes
            (r'\[quote\](.*?)\[/quote\]', r'<blockquote>\1</blockquote>'),
            
            # Code
            (r'\[code\](.*?)\[/code\]', r'<pre><code>\1</code></pre>'),
        ]
        
        for pattern, replacement in conversions:
            text = re.sub(pattern, replacement, text, flags=re.DOTALL | re.IGNORECASE)
        
        # Handle attachments
        text = re.sub(r'\[attach\](\d+)\[/attach\]', self._replace_attachment, text)
        
        # Convert newlines to <br> tags
        text = text.replace('\n', '<br>')
        
        return text
    
    def _replace_attachment(self, match):
        """Replace attachment BBCode with HTML"""
        aid = int(match.group(1))
        if aid in self.attachments:
            attachment = self.attachments[aid]
            filename = attachment['filename']
            filepath = f"attachments/{attachment['attachment']}"
            
            if attachment['isimage']:
                return f'<div class="attachment image"><img src="{filepath}" alt="{filename}" style="max-width: 100%;"><br><small>附件: {filename}</small></div>'
            else:
                return f'<div class="attachment file"><a href="{filepath}" download="{filename}">{filename}</a></div>'
        
        return f'[附件 {aid} 未找到]'
    
    def generate_static_website(self):
        """Generate the static website"""
        print("正在生成靜態網站...")
        
        # Create output directory
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Copy attachments
        self._copy_attachments()
        
        # Generate CSS
        self._generate_css()
        
        # Generate index page
        self._generate_index()
        
        # Generate forum pages
        self._generate_forum_pages()
        
        # Generate thread pages
        self._generate_thread_pages()
        
        print(f"網站生成完成! 輸出目錄: {self.output_dir}")
    
    def _copy_attachments(self):
        """Copy attachment files to output directory"""
        src_attachments = Path(self.attachments_dir)
        dst_attachments = Path(self.output_dir) / "attachments"
        
        if src_attachments.exists():
            print("正在複製附件...")
            if dst_attachments.exists():
                shutil.rmtree(dst_attachments)
            shutil.copytree(src_attachments, dst_attachments)
            print(f"附件複製完成: {dst_attachments}")
    
    def _generate_css(self):
        """Generate CSS file"""
        css_content = """
body {
    font-family: "Microsoft JhengHei", "Helvetica Neue", Arial, sans-serif;
    line-height: 1.6;
    margin: 0;
    padding: 20px;
    background-color: #f5f5f5;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
    background-color: white;
    padding: 20px;
    border-radius: 8px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}

h1, h2, h3 {
    color: #0066cc;
    border-bottom: 2px solid #0066cc;
    padding-bottom: 10px;
}

.forum-list {
    list-style: none;
    padding: 0;
}

.forum-item {
    margin: 10px 0;
    padding: 15px;
    background-color: #f8f9fa;
    border-radius: 5px;
    border-left: 4px solid #0066cc;
}

.forum-item a {
    text-decoration: none;
    color: #0066cc;
    font-weight: bold;
}

.forum-item a:hover {
    text-decoration: underline;
}

.thread-list {
    list-style: none;
    padding: 0;
}

.thread-item {
    margin: 10px 0;
    padding: 10px;
    background-color: #f8f9fa;
    border-radius: 5px;
}

.thread-title {
    font-weight: bold;
    color: #0066cc;
}

.thread-meta {
    color: #666;
    font-size: 0.9em;
    margin-top: 5px;
}

.post {
    margin: 20px 0;
    padding: 15px;
    background-color: #fafafa;
    border-radius: 5px;
    border-left: 3px solid #28a745;
}

.post.first-post {
    border-left-color: #0066cc;
    background-color: #f0f8ff;
}

.post-header {
    background-color: #e9ecef;
    padding: 10px;
    border-radius: 5px 5px 0 0;
    margin: -15px -15px 15px -15px;
}

.post-author {
    font-weight: bold;
    color: #495057;
}

.post-date {
    color: #6c757d;
    font-size: 0.9em;
    float: right;
}

.post-content {
    margin-top: 10px;
    line-height: 1.6;
}

.post-content img {
    max-width: 100%;
    height: auto;
    border-radius: 5px;
}

blockquote {
    border-left: 4px solid #ccc;
    margin: 10px 0;
    padding: 10px 20px;
    background-color: #f9f9f9;
    font-style: italic;
}

.attachment {
    margin: 10px 0;
    padding: 10px;
    background-color: #e9ecef;
    border-radius: 5px;
    border: 1px solid #dee2e6;
}

.attachment.image {
    text-align: center;
}

.attachment a {
    color: #0066cc;
    text-decoration: none;
}

.attachment a:hover {
    text-decoration: underline;
}

.navigation {
    margin: 20px 0;
    padding: 10px;
    background-color: #e9ecef;
    border-radius: 5px;
}

.navigation a {
    color: #0066cc;
    text-decoration: none;
    margin-right: 15px;
}

.navigation a:hover {
    text-decoration: underline;
}

.youtube-container {
    position: relative;
    width: 100%;
    height: 0;
    padding-bottom: 56.25%; /* 16:9 aspect ratio */
    margin: 10px 0;
}

.youtube-container iframe {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
}

pre {
    background-color: #f8f9fa;
    border: 1px solid #dee2e6;
    border-radius: 5px;
    padding: 10px;
    overflow-x: auto;
}

.stats {
    margin-top: 20px;
    padding: 10px;
    background-color: #e7f3ff;
    border-radius: 5px;
    color: #0066cc;
}
"""
        
        with open(os.path.join(self.output_dir, 'style.css'), 'w', encoding='utf-8') as f:
            f.write(css_content)
    
    def _generate_index(self):
        """Generate main index page"""
        html_content = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SonicHub 討論區備份</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div class="container">
        <h1>🦔 SonicHub 討論區備份</h1>
        <p>歡迎來到 SonicHub 討論區的靜態備份網站！這裡保存了所有珍貴的討論內容和回憶。</p>
        
        <div class="stats">
            📊 統計資料: {len(self.forums)} 個討論版塊 | {len(self.posts)} 篇文章 | {len(self.attachments)} 個附件
        </div>
        
        <h2>討論版塊</h2>
        <ul class="forum-list">
"""
        
        # Sort forums by ID
        sorted_forums = sorted(self.forums.items(), key=lambda x: x[0])
        
        for fid, forum in sorted_forums:
            if forum['type'] in ['forum', 'group']:  # Only show main forums
                thread_count = len([tid for tid in self.threads if any(p['fid'] == fid for p in self.threads[tid])])
                post_count = len(forum['posts'])
                
                html_content += f"""            <li class="forum-item">
                <a href="forum_{fid}.html">{html.escape(forum['name'])}</a>
                <div class="thread-meta">{thread_count} 個主題 | {post_count} 篇文章</div>
            </li>
"""
        
        html_content += """        </ul>
        
        <div style="margin-top: 40px; text-align: center; color: #666; font-size: 0.9em;">
            <p>🕐 備份時間: 2018年2月15日</p>
            <p>由 SonicHub SQL 轉換器生成 | 靜態網站版本</p>
        </div>
    </div>
</body>
</html>"""
        
        with open(os.path.join(self.output_dir, 'index.html'), 'w', encoding='utf-8') as f:
            f.write(html_content)
    
    def _generate_forum_pages(self):
        """Generate individual forum pages"""
        for fid, forum in self.forums.items():
            if forum['type'] not in ['forum', 'group']:
                continue
                
            # Get all threads for this forum
            forum_threads = []
            for tid, thread_posts in self.threads.items():
                if thread_posts and thread_posts[0]['fid'] == fid:
                    first_post = thread_posts[0]  # Original post
                    forum_threads.append({
                        'tid': tid,
                        'title': first_post['subject'] or '(無標題)',
                        'author': first_post['author'],
                        'dateline': first_post['dateline'],
                        'replies': len(thread_posts) - 1,
                        'posts': thread_posts
                    })
            
            # Sort threads by date (newest first)
            forum_threads.sort(key=lambda t: t['dateline'], reverse=True)
            
            html_content = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(forum['name'])} - SonicHub 討論區備份</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div class="container">
        <div class="navigation">
            <a href="index.html">🏠 首頁</a>
        </div>
        
        <h1>📁 {html.escape(forum['name'])}</h1>
        <p>共 {len(forum_threads)} 個主題，{len(forum['posts'])} 篇文章</p>
        
        <ul class="thread-list">
"""
            
            for thread in forum_threads:
                date_str = datetime.fromtimestamp(thread['dateline']).strftime('%Y-%m-%d %H:%M')
                html_content += f"""            <li class="thread-item">
                <div class="thread-title">
                    <a href="thread_{thread['tid']}.html">{html.escape(thread['title'])}</a>
                </div>
                <div class="thread-meta">
                    👤 {html.escape(thread['author'])} | 🕐 {date_str} | 💬 {thread['replies']} 個回覆
                </div>
            </li>
"""
            
            html_content += """        </ul>
    </div>
</body>
</html>"""
            
            with open(os.path.join(self.output_dir, f'forum_{fid}.html'), 'w', encoding='utf-8') as f:
                f.write(html_content)
    
    def _generate_thread_pages(self):
        """Generate individual thread pages"""
        for tid, posts in self.threads.items():
            if not posts:
                continue
            
            first_post = posts[0]
            forum = self.forums.get(first_post['fid'], {'name': '未知版塊'})
            
            html_content = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(first_post['subject'] or '(無標題)')} - SonicHub 討論區備份</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div class="container">
        <div class="navigation">
            <a href="index.html">🏠 首頁</a>
            <a href="forum_{first_post['fid']}.html">📁 {html.escape(forum['name'])}</a>
        </div>
        
        <h1>{html.escape(first_post['subject'] or '(無標題)')}</h1>
        
"""
            
            for i, post in enumerate(posts):
                date_str = datetime.fromtimestamp(post['dateline']).strftime('%Y-%m-%d %H:%M:%S')
                post_class = 'post first-post' if i == 0 else 'post'
                
                html_content += f"""        <div class="{post_class}">
            <div class="post-header">
                <span class="post-author">👤 {html.escape(post['author'])}</span>
                <span class="post-date">🕐 {date_str}</span>
                <div style="clear: both;"></div>
            </div>
            
            <div class="post-content">
                {self.convert_bbcode_to_html(post['message'])}
            </div>
        </div>
        
"""
            
            html_content += """    </div>
</body>
</html>"""
            
            with open(os.path.join(self.output_dir, f'thread_{tid}.html'), 'w', encoding='utf-8') as f:
                f.write(html_content)


def main():
    """Main function"""
    print("🦔 SonicHub 討論區 SQL 轉靜態網站工具")
    print("=" * 50)
    
    converter = SonicHubConverter('sonichub_forum.sql', 'website', 'attachments')
    
    try:
        # Parse SQL file
        converter.parse_sql_file()
        
        # Generate static website
        converter.generate_static_website()
        
        print("\n✅ 轉換完成!")
        print(f"📁 請查看 '{converter.output_dir}' 資料夾中的靜態網站")
        print("🌐 開啟 index.html 開始瀏覽")
        
    except Exception as e:
        print(f"❌ 轉換過程中發生錯誤: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()