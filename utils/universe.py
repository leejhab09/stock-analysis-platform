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
