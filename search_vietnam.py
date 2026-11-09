"""Ví dụ: python search_vietnam.py --province 'Hà Nội' --area-max 100 --export results/ha_noi.csv"""
import argparse
import json
from src.vietnam_data import ROOT
from src.vietnam_search import search_data
from src.vietnam_queries import validate_filters


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--province'); p.add_argument('--property-type')
    p.add_argument('--area-min',type=float,default=50); p.add_argument('--area-max',type=float,default=150)
    p.add_argument('--price-min',type=float,default=1); p.add_argument('--price-max',type=float,default=10e9)
    p.add_argument('--limit',type=int,default=20)
    p.add_argument('--export',type=str,help='Đường dẫn CSV chứa toàn bộ hàng khớp điều kiện')
    a=p.parse_args()
    try:
        filters=validate_filters(dict(province=a.province,property_type=a.property_type,area_min=a.area_min,
                                      area_max=a.area_max,price_min=a.price_min,price_max=a.price_max))
        result=search_data(ROOT/'data/vietnam/processed/vietnam_clean.parquet',filters,a.limit,a.export)
    except (ValueError,FileNotFoundError) as error:
        p.error(str(error))
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__': main()
