# Limitations

These are known and documented, not hidden. Each one gives what was observed and why it matters.

| Limitation | Evidence | Impact |
|---|---|---|
| **No real-site validation** | All evaluation footage is public (datasets, Wikimedia Commons and Mixkit clips) | Results may not transfer to a given site's cameras, angles and lighting |
| **Distant and small workers** | On two distant, low-quality rooftop clips, no model found any of the 5–7 bare-headed workers; even person detection barely worked | Wide-angle cameras covering large areas will miss violations |
| **Night-time footage** | One night clip tested (good results, but n = 1); low light and glare were not studied systematically | Night performance is unknown in general |
| **Cross-domain generalisation** | Construction-PPE test mAP50 0.427 against Mendeley 0.671; large swings between label conventions (shell against full-head boxes) | Scores depend strongly on how a site's data would be labelled |
| **Worker ID fragmentation** | 47 IDs for fewer people across ten unseen clips; IDs can split after occlusion | Counts are *tracks*, not people; duplicate suppression reduces but does not remove repeat alerts |
| **Annotation problems** | Partial labels in Construction-PPE and Mendeley; derived SH17 `no_helmet` labels with about 1 in 66 wrong in a sample | Precision on common val is a lower bound; some training noise remains |
| **Limited unseen-video evaluation** | 10 unseen clips plus 5 demo clips, minutes of footage in total | Low statistical power; confidence intervals not computed |
| **No sense of context** | Bare-headed people in an archive film and an office interview were flagged | The system cannot tell where a hard hat is required |
| **Headwear ambiguity** | Caps, hoods and scarves count as no hard hat by design; white shells seen from behind were a known failure mode before the 0.60 threshold | Possible false alarms or misses for unusual headwear |
| **Thresholds tuned on little footage** | 0.60 chosen from validation and five demo clips | Each site should re-tune |
| **Fairness not assessed** | No analysis by skin tone, hair type or religious headwear | Error rates may differ between groups |
| **Single camera, single run** | One active run per server (shared tracker) | Not a multi-camera system as built |
| **Processing speed varies** | 41–60 FPS in the app on one day, 20–40 FPS later when the GPU stayed at low clocks | Live-camera use needs headroom and monitoring |
| **Licensing** | SH17 is CC BY-NC-SA 4.0; Ultralytics is AGPL-3.0 | The trained model is non-commercial; weights are not published here |
| **Privacy** | Evidence frames show identifiable people | Real use needs consent, notices and retention rules |
