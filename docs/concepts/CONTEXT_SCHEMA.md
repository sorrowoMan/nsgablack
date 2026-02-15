# Context Schema & 莽聰聼氓聭陆氓聭篓忙聹聼

忙聹卢忙隆聠忙聻露忙聤聤 `context` 氓陆聯盲陆聹芒聙聹猫驴聬猫隆聦忙聴露猫炉颅盲鹿聣忙聙禄莽潞驴芒聙聺茫聙? 
盲赂潞盲潞聠茅聛驴氓聟聧芒聙聹氓颅聴忙庐碌氓聬芦盲鹿聣盲赂聧忙赂?+ 莽录聯氓颅聵忙路路氓聟楼 + 忙聴聽忙鲁聲茅聡聧忙聰戮芒聙聺茂录聦猫驴聶茅聡聦莽禄聶氓聡潞**莽潞娄氓庐職氓聦聳莽職聞莽聰聼氓聭陆氓聭篓忙聹聼氓聢聠莽卤禄**盲赂?*忙聹聙氓掳聫茅聡聧忙聰戮忙聹潞氓聢?*茫聙?
## 盲赂聣盲赂陋忙聽赂氓驴聝茅聴庐茅垄聵茂录聢莽聸麓忙聨楼氓聸聻莽颅聰茂录聣

### 1) context 猫聝陆氓聬娄莽聰卤芒聙聹氓聢聺氓搂聥忙聺隆盲禄?+ event芒聙聺茅聡聧忙聰戮氓戮聴氓聢掳茂录聼
**氓聫炉盲禄楼茂录聦盲陆聠氓聫陋茅聮聢氓炉鹿芒聙聹氓聫炉茅聡聧忙聰戮氓颅聴忙庐碌芒聙聺茫聙?*  
`cache` 莽卤禄氓颅聴忙庐碌茂录聢氓娄?population/objectives 莽颅聣茂录聣猫垄芦猫搂聠盲赂潞忙聙搂猫聝陆莽录聯氓颅聵茂录聦盲赂聧盲驴聺猫炉聛氓聫炉茅聡聧忙聰戮茫聙? 
盲陆聽氓聫炉盲禄楼茂录職

- 氓聟聢莽聰篓 `strip_context_for_replay()` 氓戮聴氓聢掳**氓聫炉茅聡聧忙聰戮氓颅聬茅聸?*
- 氓聠聧莽聰篓 `replay_context(base, events)` 氓聸聻忙聰戮

猫驴聶氓掳卤忙聵聨莽隆庐盲潞聠茂录職芒聙聹氓聫炉茅聡聧忙聰戮茅聝篓氓聢聠芒聙聺盲赂聨芒聙聹莽录聯氓颅聵茅聝篓氓聢聠芒聙聺莽職聞猫戮鹿莽聲聦茫聙?
### 2) context 盲赂颅忙聵炉氓聬娄忙路路氓聟楼盲潞聠芒聙聹盲赂潞盲潞聠忙聳鹿盲戮驴猫庐隆莽庐聴芒聙聺莽職聞莽录聯氓颅聵茂录?**忙聵炉莽職聞茂录聦盲赂聰猫驴聶忙聵炉氓聟聛猫庐赂莽職聞茫聙?*  
盲陆聠猫娄聛**忙聵戮氓录聫氓聦潞氓聢聠**茂录?
- `cache`茂录職莽潞炉忙聙搂猫聝陆莽录聯氓颅聵茂录聦茅聡聧忙聰戮忙聴露氓聫炉盲赂垄氓录?- `runtime`茂录職猫驴聬猫隆聦忙聹聼莽聤露忙聙聛茂录聢generation/step/phase茂录?- `input`茂录職忙聺楼猫聡陋茅聴庐茅垄聵氓庐職盲鹿?氓庐聻茅陋聦猫戮聯氓聟楼

### 3) context 氓颅聴忙庐碌忙聵炉氓聬娄忙聹聣忙聵聨莽隆庐莽職聞猫炉颅盲鹿聣莽聰聼氓聭陆氓聭篓忙聹聼茂录?**忙聹聣茫聙?*  
氓聹?`utils/context/context_schema.py` 茅聡聦氓庐職盲鹿聣盲潞聠茂录?
```
input / runtime / derived / cache / output / event
```

氓鹿露忙聫聬盲戮?`get_context_lifecycle()` 莽聰聼忙聢聬氓颅聴忙庐碌芒聠聮莽聰聼氓聭陆氓聭篓忙聹聼忙聵聽氓掳聞茫聙?
---

## 莽聰聼氓聭陆氓聭篓忙聹聼氓聢聠莽卤禄茂录聢氓禄潞猫庐庐茂录聣

| 氓聢聠莽卤禄 | 氓聬芦盲鹿聣 | 莽陇潞盲戮聥 |
|---|---|---|
| input | 茅聴庐茅垄聵/氓庐聻茅陋聦莽職聞莽篓鲁氓庐職猫戮聯氓聟?| bounds / constraints / metadata |
| runtime | 猫驴聬猫隆聦忙聹聼莽聤露忙聙?| generation / step / phase_id |
| derived | 莽禄聼猫庐隆/忙麓戮莽聰聼忙聦聡忙聽聡 | metrics |
| cache | 忙聙搂猫聝陆莽录聯氓颅聵茂录聢盲赂聧盲驴聺猫炉聛氓聫炉茅聡聧忙聰戮茂录聣 | population / objectives |
| output | 猫戮聯氓聡潞莽禄聯忙聻聞 | pareto_solutions |
| event | 盲潞聥盲禄露盲赂聨氓聨聠氓聫?| history / context_events |

---

## 盲禄拢莽聽聛忙聨楼氓聫拢茅聙聼猫搂聢

```python
from nsgablack.utils.context import (
    RUNTIME_CONTEXT_SCHEMA,
    validate_context,
    get_context_lifecycle,
    strip_context_for_replay,
    replay_context,
    record_context_event,
)
```

### 1) 忙聽隆茅陋聦茂录聢氓录卤忙聽隆茅陋聦茂录?```python
warnings = validate_context(ctx)
```

### 2) 莽聰聼氓聭陆氓聭篓忙聹聼忙聵聽氓掳聞
```python
lifecycle = get_context_lifecycle(ctx)
```

### 3) 盲潞聥盲禄露猫庐掳氓陆聲 + 茅聡聧忙聰戮
```python
record_context_event(ctx, kind="set", key="phase_id", value=2, source="dynamic_switch")
replayed = replay_context(strip_context_for_replay(ctx), ctx.get("context_events", []))
```

---

## 莽潞娄氓庐職氓禄潞猫庐庐

- **莽录聯氓颅聵茅聸聠盲赂颅忙聰戮氓聹篓 cache 莽卤禄氓颅聴忙庐?*茂录聦盲赂聧猫娄聛忙路路氓聟?input/runtime茫聙?- **盲潞聥盲禄露氓聫陋猫驴陆氓聤?*茂录聦盲赂聧猫娄聛茅聡聧氓聠聶茂录聦盲戮驴盲潞聨茅聡聧忙聰戮盲赂聨氓庐隆猫庐隆茫聙?- 氓鹿露猫隆聦猫炉聞盲录掳氓聫陋盲陆驴莽聰?`MinimalEvaluationContext`茫聙?
---

## 莽禄聯猫庐潞

`context` 盲赂聧忙聵炉芒聙聹茅職聫盲戮驴氓隆聻氓颅聴忙庐碌莽職?dict芒聙聺茫聙? 
氓庐聝忙聵炉盲赂聙盲赂陋氓聫炉氓庐隆猫庐隆莽職?*猫驴聬猫隆聦忙聴露莽禄聯忙聻?*茫聙? 
氓娄聜忙聻聹茅聛碌氓戮陋莽聰聼氓聭陆氓聭篓忙聹聼氓聢聠莽卤禄茂录聦忙隆聠忙聻露氓聫炉盲禄楼氓庐聻莽聨掳茂录職

1) 氓聫炉茅聡聧忙聰? 
2) 氓聫炉猫搂拢茅聡? 
3) 氓聫炉忙聣漏氓卤?

