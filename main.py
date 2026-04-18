# ... (상단 설정 부분 동일)

def scan_page(session, target_url, prev_url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': prev_url
        }
        proxy_url = f"{GOOGLE_PROXY_URL}?url={target_url}"
        response = session.get(proxy_url, headers=headers, timeout=30)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 상품 항목 추출
        items = soup.select('.main-product-tab-goods > li') or soup.find_all('li', attrs={'data-childno': True})
        found_in_page = 0
        
        for item in items:
            link_tag = item.find('a', href=re.compile(r'gno='))
            if not link_tag: continue
            
            p_id = link_tag['href'].split('gno=')[-1].split('&')[0]
            name_tag = item.find('h5') or item.select_one('.font-15')
            p_name = name_tag.get_text(strip=True) if name_tag else "상품명 미상"
            p_url = f"https://www.bnkrmall.co.kr{link_tag['href']}" if link_tag['href'].startswith('/') else link_tag['href']

            # [핵심] 품절 판정 로직
            # 상품 항목 HTML 전체에서 'sold_out'이나 '품절' 단어가 있는지 찾습니다.
            item_html = str(item).lower()
            is_sold_out = "sold_out" in item_html or "품절" in item.get_text()
            current_status = "품절" if is_sold_out else "재고있음"
            
            if p_id in tracked_products:
                # '품절'이었다가 '재고있음'으로 바뀌는 순간을 포착!
                if tracked_products[p_id]['status'] == "품절" and current_status == "재고있음":
                    send_message(f"🚨 [재입고 포착!]\n📦 {p_name}\n🔗 {p_url}")
            
            tracked_products[p_id] = {"name": p_name, "status": current_status}
            found_in_page += 1
            
        return found_in_page
    except Exception as e:
        print(f"❌ 스캔 중 오류 발생: {e}")
        return 0

# ... (이하 명령어 처리 및 무한루프 로직 동일)
