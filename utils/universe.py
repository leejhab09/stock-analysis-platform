"""
universe.py
섹터별 종목 유니버스 정의
"""

UNIVERSE = {
    "💻 빅테크": {
        "tickers": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "ORCL", "CRM", "ADBE", "NOW"],
        "desc": "애플, 마이크로소프트, 구글, 아마존, 메타 등"
    },
    "🔬 반도체": {
        "tickers": ["NVDA", "AMD", "INTC", "QCOM", "AVGO", "ASML", "TSM", "MU", "LRCX", "AMAT", "KLAC", "MRVL"],
        "desc": "엔비디아, AMD, ASML, TSMC 등"
    },
    "🤖 AI·소프트웨어": {
        "tickers": ["PLTR", "AI", "SNOW", "PATH", "DDOG", "MDB", "NET", "ZS", "CRWD", "S"],
        "desc": "팔란티어, C3.ai, 스노우플레이크 등 AI·클라우드"
    },
    "🏦 금융": {
        "tickers": ["JPM", "BAC", "GS", "MS", "V", "MA", "WFC", "C", "BX", "SCHW"],
        "desc": "JP모건, 뱅크오브아메리카, 비자, 마스터카드 등"
    },
    "🏥 헬스케어": {
        "tickers": ["JNJ", "UNH", "ABBV", "LLY", "PFE", "MRK", "BMY", "AMGN", "GILD", "ISRG"],
        "desc": "존슨앤드존슨, 유나이티드헬스, 일라이릴리 등"
    },
    "⚡ 에너지": {
        "tickers": ["XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX", "OXY", "HAL", "DVN"],
        "desc": "엑슨모빌, 쉐브론, ConocoPhillips 등"
    },
    "🛒 소비재": {
        "tickers": ["WMT", "COST", "MCD", "SBUX", "NKE", "HD", "TGT", "LOW", "TJX", "AMZN"],
        "desc": "월마트, 코스트코, 맥도날드, 나이키 등"
    },
    "🏭 산업재": {
        "tickers": ["CAT", "BA", "GE", "HON", "DE", "UPS", "RTX", "LMT", "NOC", "MMM"],
        "desc": "캐터필러, 보잉, GE, 허니웰, UPS 등"
    },
    "📡 통신·미디어": {
        "tickers": ["NFLX", "DIS", "CMCSA", "T", "VZ", "TMUS", "SPOT", "WBD", "PARA"],
        "desc": "넷플릭스, 디즈니, AT&T, 스포티파이 등"
    },
    "🔋 친환경·EV": {
        "tickers": ["TSLA", "RIVN", "LCID", "NIO", "LI", "XPEV", "ENPH", "SEDG", "FSLR", "PLUG"],
        "desc": "테슬라, 리비안, NIO, 엔페이스 등"
    },
    "🏗️ 부동산·리츠": {
        "tickers": ["PLD", "AMT", "EQIX", "SPG", "O", "DLR", "PSA", "AVB", "EQR", "WELL"],
        "desc": "프롤로지스, 아메리칸타워, 에퀴닉스 등"
    },
    "🌍 글로벌 ETF": {
        "tickers": ["SPY", "QQQ", "IWM", "EFA", "EEM", "VNQ", "GLD", "TLT", "HYG", "VIG"],
        "desc": "S&P500, 나스닥100, 러셀2000, 신흥국 ETF 등"
    },
}

# 전체 티커 (중복 제거)
ALL_TICKERS = list(dict.fromkeys(
    t for sector in UNIVERSE.values() for t in sector["tickers"]
))

# S&P 500 인기 30 (퀵 프리셋)
SP500_TOP30 = [
    "AAPL","MSFT","NVDA","AMZN","META","GOOGL","TSLA","BRK-B",
    "JPM","V","UNH","XOM","LLY","AVGO","MA","JNJ","HD","ORCL",
    "BAC","MRK","CVX","COST","ABBV","PFE","KO","WMT","CRM","MCD","NFLX","QCOM"
]

NASDAQ_TOP20 = [
    "AAPL","MSFT","NVDA","AMZN","META","GOOGL","TSLA","AVGO",
    "COST","ASML","NFLX","AMD","QCOM","ADBE","INTC","MU","TXN","AMAT","PANW","LRCX"
]

MOMENTUM_UNIVERSE = [
    "NVDA","META","MSFT","AMZN","GOOGL","AAPL","ASML","LLY",
    "NFLX","CRM","NOW","CRWD","PLTR","AVGO","TSM","AMD","MA","V","UNH","HD"
]

# ── 국내 주식 유니버스 ────────────────────────────────────────
KR_UNIVERSE = {
    "🔵 반도체·IT": {
        "tickers": ["005930.KS","000660.KS","035420.KS","035720.KS","066570.KS","028260.KS","003670.KS","036570.KS","251270.KS","263750.KQ"],
        "desc": "삼성전자, SK하이닉스, NAVER, 카카오, LG전자, 삼성물산, SK텔레콤, NC소프트"
    },
    "🚗 자동차·배터리": {
        "tickers": ["005380.KS","000270.KS","012330.KS","051910.KS","006400.KS","207940.KS","096770.KS","009150.KS","011070.KS","247540.KQ"],
        "desc": "현대차, 기아, 현대모비스, LG화학, 삼성SDI, 삼성바이오로직스, SK이노베이션"
    },
    "🏦 금융": {
        "tickers": ["105560.KS","055550.KS","086790.KS","316140.KS","032830.KS","138930.KS","024110.KS","039490.KS","071050.KS","175330.KS"],
        "desc": "KB금융, 신한지주, 하나금융, 우리금융, 삼성생명, BNK금융, IBK기업은행"
    },
    "🧬 바이오·헬스": {
        "tickers": ["068270.KS","068760.KQ","091990.KQ","145020.KQ","326030.KQ","196170.KQ","009290.KS","128940.KS","051900.KS","006800.KS"],
        "desc": "셀트리온, 셀트리온헬스케어, 알테오젠, 유한양행, 한미약품"
    },
    "🏗️ 건설·화학·소재": {
        "tickers": ["000830.KS","010130.KS","011170.KS","042660.KS","010950.KS","011790.KS","033780.KS","161390.KS","004020.KS","047050.KS"],
        "desc": "삼성물산, 고려아연, 롯데케미칼, 대한항공, S-Oil, 현대건설"
    },
    "📦 유통·소비재": {
        "tickers": ["139480.KS","004170.KS","023530.KS","069960.KS","111770.KS","071840.KS","007070.KS","282330.KS","011780.KS","009830.KS"],
        "desc": "이마트, 신세계, 롯데쇼핑, 현대백화점, BGF리테일"
    },
    "📊 ETF (국내)": {
        "tickers": ["069500.KS","114800.KS","122630.KS","226490.KS","252670.KS","091160.KS","139220.KS","148020.KS","305720.KS","261220.KS"],
        "desc": "KODEX200, KODEX인버스, KODEX레버리지, TIGER반도체, KODEX코스닥150"
    },
}

KR_ALL_TICKERS = list(dict.fromkeys(
    t for sector in KR_UNIVERSE.values() for t in sector["tickers"]
))

KR_KOSPI_TOP20 = [
    "005930.KS","000660.KS","005380.KS","051910.KS","006400.KS",
    "207940.KS","035420.KS","000270.KS","105560.KS","055550.KS",
    "068270.KS","012330.KS","028260.KS","035720.KS","066570.KS",
    "032830.KS","003670.KS","096770.KS","086790.KS","316140.KS"
]

KR_MOMENTUM_UNIVERSE = [
    "005930.KS","000660.KS","035420.KS","207940.KS","051910.KS",
    "006400.KS","068270.KS","035720.KS","005380.KS","000270.KS",
    "105560.KS","055550.KS","012330.KS","066570.KS","003670.KS"
]
