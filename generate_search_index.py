#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate search index for SonicHub static website
Extracts searchable data from HTML files and creates a JSON index
"""

import os
import json
import re
from bs4 import BeautifulSoup
from pathlib import Path

def extract_text_content(html_content):
    """Extract plain text from HTML, removing tags but preserving structure"""
    # Simple HTML tag removal for search indexing
    text = re.sub(r'<br\s*/?>', ' ', html_content)  # Replace <br> with space
    text = re.sub(r'<[^>]+>', '', text)  # Remove HTML tags
    text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
    return text.strip()

def parse_thread_file(file_path):
    """Parse a thread HTML file and extract searchable data"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        soup = BeautifulSoup(content, 'html.parser')
        
        # Extract title from h1 tag
        title_elem = soup.find('h1')
        title = title_elem.text.strip() if title_elem else ""
        
        # Extract all posts
        posts = []
        post_elements = soup.find_all('div', class_='post')
        
        for post_elem in post_elements:
            # Extract author
            author_elem = post_elem.find('span', class_='post-author')
            author = author_elem.text.replace('👤 ', '').strip() if author_elem else ""
            
            # Extract date
            date_elem = post_elem.find('span', class_='post-date')
            date = date_elem.text.replace('🕐 ', '').strip() if date_elem else ""
            
            # Extract content
            content_elem = post_elem.find('div', class_='post-content')
            if content_elem:
                content_html = str(content_elem)
                content_text = extract_text_content(content_html)
                
                posts.append({
                    'author': author,
                    'date': date,
                    'content': content_text
                })
        
        return {
            'file': os.path.basename(file_path),
            'title': title,
            'posts': posts
        }
    
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
        return None

def parse_forum_file(file_path):
    """Parse a forum HTML file and extract thread information"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        soup = BeautifulSoup(content, 'html.parser')
        
        # Extract forum title
        title_elem = soup.find('h1')
        forum_title = title_elem.text.replace('📁 ', '').strip() if title_elem else ""
        
        # Extract thread links and titles
        threads = []
        thread_elements = soup.find_all('li', class_='thread-item')
        
        for thread_elem in thread_elements:
            title_elem = thread_elem.find('div', class_='thread-title')
            if title_elem:
                link_elem = title_elem.find('a')
                if link_elem:
                    thread_link = link_elem.get('href')
                    thread_title = link_elem.text.strip()
                    
                    # Extract meta info
                    meta_elem = thread_elem.find('div', class_='thread-meta')
                    meta_text = meta_elem.text.strip() if meta_elem else ""
                    
                    threads.append({
                        'link': thread_link,
                        'title': thread_title,
                        'meta': meta_text
                    })
        
        return {
            'file': os.path.basename(file_path),
            'title': forum_title,
            'threads': threads
        }
    
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
        return None

def generate_search_index(website_dir):
    """Generate complete search index from website files"""
    website_path = Path(website_dir)
    search_index = {
        'threads': {},
        'forums': {},
        'generated_at': str(Path(__file__).stat().st_mtime)
    }
    
    print("Generating search index...")
    
    # Parse all thread files
    thread_files = list(website_path.glob('thread_*.html'))
    print(f"Found {len(thread_files)} thread files")
    
    for thread_file in thread_files:
        thread_data = parse_thread_file(thread_file)
        if thread_data:
            search_index['threads'][thread_data['file']] = thread_data
    
    # Parse all forum files
    forum_files = list(website_path.glob('forum_*.html'))
    print(f"Found {len(forum_files)} forum files")
    
    for forum_file in forum_files:
        forum_data = parse_forum_file(forum_file)
        if forum_data:
            search_index['forums'][forum_data['file']] = forum_data
    
    return search_index

def main():
    website_dir = "website"
    output_file = os.path.join(website_dir, "search_index.json")
    
    # Generate search index
    index = generate_search_index(website_dir)
    
    # Write to JSON file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    
    print(f"Search index generated: {output_file}")
    print(f"Indexed {len(index['threads'])} threads and {len(index['forums'])} forums")

if __name__ == "__main__":
    main()