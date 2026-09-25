import json
rep = json.load(open('sandbox_report.json', encoding='utf-8'))
print('TOTALS', rep['totals'])
print()
for r in rep['results']:
    if r['status'] != 'PASS':
        note = r['note'][:320].replace('\n', ' ')
        print("[%s] %-22s %-42s %s" % (r['status'], r['id'], r['feature'][:40], note))