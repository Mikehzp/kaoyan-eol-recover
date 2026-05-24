#!/usr/bin/env python3
"""
中国教育在线 报录比数据 - 多通道恢复工具
=========================================
使用多个通道尝试恢复数据，不依赖单一源。
"""
import json, os, time, re

INDEX = os.path.join(os.path.dirname(__file__), "eol_index_full.json")
OUTPUT = os.path.join(os.path.dirname(__file__), "recovered_data")
os.makedirs(OUTPUT, exist_ok=True)

# 优先恢复的 CS 强校
PRIORITY = ["北京邮电大学", "西安电子科技大学", "杭州电子科技大学", 
            "南京邮电大学", "深圳大学", "浙江大学", "上海交通大学",
            "华南理工大学", "武汉大学", "国防科技大学", "华东师范大学",
            "哈尔滨工业大学", "同济大学", "北京科技大学", "东北大学"]

def load_index():
    with open(INDEX) as f:
        return json.load(f)

def try_wayback(url, timeout=15):
    """尝试从 Wayback Machine 获取页面 (已保存的快照)"""
    import urllib.request, ssl
    # 从 URL 推断存档年份
    m = re.search(r'/(20\d{2})/', url)
    year = m.group(1) if m else "2021"
    
    wm_urls = [
        f"https://web.archive.org/web/{year}1231000000/{url}",
        f"https://web.archive.org/web/{year}0701000000/{url}",
    ]
    
    for wm_url in wm_urls:
        try:
            ctx = ssl._create_unverified_context()
            req = urllib.request.Request(wm_url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
            html = resp.read().decode('utf-8', 'ignore')
            if '报考' in html or '录取' in html or '报名' in html:
                print(f"      ✅ Wayback 存档可用: {wm_url[:80]}")
                return html, "wayback"
        except:
            continue
    return None, None

def try_direct(url, timeout=10):
    """直接访问原始 URL (少数可能还活着)"""
    import urllib.request, ssl
    try:
        ctx = ssl._create_unverified_context()
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        html = resp.read().decode('utf-8', 'ignore')
        if len(html) > 1000 and '报考' in html:
            print(f"      ✅ 原始页面仍可访问")
            return html, "direct"
    except:
        pass
    return None, None

def try_bing_cache(url, timeout=10):
    """尝试 Bing 快照"""
    import urllib.request, ssl
    bing_url = f"https://cc.bingj.com/cache.aspx?d=4&s=AGOdhGdNxLr8F7npN8PMwJ0I73V0vQ&mkt=zh-CN&setlang=zh-CN&w={url}"
    try:
        ctx = ssl._create_unverified_context()
        req = urllib.request.Request(bing_url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        html = resp.read().decode('utf-8', 'ignore')
        if '报考' in html:
            print(f"      ✅ Bing 快照可用")
            return html, "bing"
    except:
        pass
    return None, None

def parse_table(html):
    """解析 EOL 报录比表格"""
    tables = re.findall(r'<table[^>]*>(.*?)</table>', html, re.DOTALL | re.IGNORECASE)
    results = []
    
    for table_html in tables:
        trs = re.findall(r'<tr[^>]*>(.*?)</tr>', table_html, re.DOTALL)
        for tr in trs:
            cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', tr, re.DOTALL)
            cells = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
            if len(cells) >= 5:
                # 找包含数字的行 (报考人数/录取人数)
                nums = [int(re.sub(r'\D', '', c)) for c in cells if re.search(r'\d{3,}', c)]
                if len(nums) >= 2:
                    results.append(cells)
    
    return results

def main():
    print(f"中国教育在线 报录比数据恢复工具 v2.0")
    print(f"{'='*60}")
    print(f"多通道恢复: Wayback Machine → 原始页面 → Bing 快照")
    
    if not os.path.exists(INDEX):
        print(f"❌ 索引文件不存在: {INDEX}")
        return
    
    index = load_index()
    print(f"索引: {len(index)} 所学校, {sum(len(s['years']) for s in index)} 个页面\n")
    
    # 先恢复优先级高的
    target = [s for s in index if s["school"] in PRIORITY]
    print(f"优先恢复 {len(target)} 所 CS 强校...\n")
    
    total_pages = 0
    total_rows = 0
    
    for entry in target:
        school = entry["school"]
        years = entry["years"]
        
        print(f"📡 {school} ({len(years)}个年份)")
        school_data = {"school": school, "data": []}
        
        for year, url in sorted(years.items()):
            print(f"  {year}年...", end=" ")
            
            html, source = None, None
            
            # 通道1: 原始页面直连
            html, source = try_direct(url)
            
            # 通道2: Bing 快照
            if not html:
                html, source = try_bing_cache(url)
            
            # 通道3: Wayback Machine
            if not html:
                html, source = try_wayback(url)
            
            if html:
                rows = parse_table(html)
                if rows:
                    print(f"→ {len(rows)} 行数据 ({source})")
                    school_data["data"].append({"year": year, "source": source, "rows": rows})
                    total_rows += len(rows)
                else:
                    print(f"→ 有页面但未识别出表格")
            else:
                print(f"❌ 所有通道均不可达")
            
            total_pages += 1
            time.sleep(0.5)  # 礼貌间隔
        
        # 保存该校数据
        if school_data["data"]:
            out_file = os.path.join(OUTPUT, f"{school}.json")
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(school_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*60}")
    print(f"恢复完成! 尝试 {total_pages} 个页面, 提取 {total_rows} 行数据")
    print(f"数据保存在: {OUTPUT}/")
    print(f"\n完成后运行: python3 import_all.py 导入数据库")

if __name__ == "__main__":
    main()
