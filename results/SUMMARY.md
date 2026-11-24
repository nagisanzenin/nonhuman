| | baseline | Ponytail | **nonhuman** |
|---|---|---|---|
| Python | 353k | 346k (0.98×) | **201k (0.57×)** |
| TypeScript | 183k | 194k (1.06×) | **177k (0.97×)** |
| Rust | 267k | 243k (0.91×) | **185k (0.69×)** |
| C | 237k | 257k (1.08×) | **169k (0.71×)** |
| **All** | 260k | 260k (1.00×) | **183k (0.70×)** |

| per run (all languages) | baseline | Ponytail | nonhuman |
|---|---|---|---|
| model calls | 12.2 | 13.2 | 7.4 |
| output tokens | 17,461 | 16,421 | 12,356 |
| thinking tokens | 2,701 | 2,459 | 3,202 |

| hidden tests passed | baseline | Ponytail | nonhuman |
|---|---|---|---|
| functional | 499/510 | 498/510 | 498/510 |
| security | 513/516 | 513/516 | 513/516 |
