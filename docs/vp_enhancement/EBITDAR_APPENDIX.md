# EBITDAR Variant Appendix - VP Extra Credit
## Alternative Lease Treatment Analysis

**Status**: 📊 **Extra Credit Implementation**  
**Purpose**: Compare lease treatments for comprehensive analysis

---

## EBITDAR Framework Overview

**EBITDAR** = Earnings Before Interest, Taxes, Depreciation, Amortization, and **Rent**

### Key Differences vs. IFRS-16 Lease-in-Debt

| Metric | IFRS-16 (Base Case) | EBITDAR Variant |
|--------|---------------------|-----------------|
| **EBITDA Base** | €820m | €950m (+ €130m rent) |
| **Leverage Metric** | Net Debt / EBITDA | Net Debt / EBITDAR |
| **Lease Treatment** | Capitalized (€1.25bn) | Operating expense |
| **Covenant Base** | EBITDA (lower) | EBITDAR (higher) |

---

## EBITDAR Calculations

### Base Case Adjustments
```python
# IFRS-16 Base Case
base_ebitda = 820  # €m
annual_rent = 130  # €m  
lease_liability = 1250  # €m (8x rent)

# EBITDAR Variant
ebitdar = base_ebitda + annual_rent  # €950m
# No lease capitalization in this variant
```

### Leverage Comparison
```python
# IFRS-16 Approach (Base Case)
net_debt_with_leases = 6000 + 1250  # €7.25bn
leverage_ifrs16 = net_debt_with_leases / base_ebitda  # 8.8x

# EBITDAR Approach  
net_debt_traditional = 6000  # €6.0bn (no lease liability)
leverage_ebitdar = net_debt_traditional / ebitdar  # 6.3x
```

---

## Covenant Analysis - EBITDAR Framework

### Traditional Covenant Tests (EBITDAR-based)
- **ICR**: EBITDAR / Interest = €950m / €420m = **2.3x**
- **Leverage**: Net Debt / EBITDAR = €6.0bn / €950m = **6.3x**

### Comparison to IFRS-16 Covenants
| Covenant | IFRS-16 (Base) | EBITDAR Variant | Covenant Limit |
|----------|----------------|-----------------|----------------|
| **Min ICR** | 2.5x | 2.3x | 2.2x |
| **Max Leverage** | 8.4x | 6.3x | 9.0x |

**EBITDAR Insight**: Higher EBITDAR provides more covenant cushion but excludes lease risk

---

## Return Impact Analysis

### IRR Sensitivity to Lease Treatment
```python
# Base Case (IFRS-16): 9.1% IRR / 1.7x MOIC
# Drivers: €2.5bn equity, €3.9bn exit equity

# EBITDAR Variant Impact:
# - Lower initial equity (no lease liability)
# - Same enterprise value at exit
# - Rent continues as operating expense
# - Slightly different cash generation profile
```

### Exit Multiple Comparison
| Treatment | Exit EBITDA/R | Multiple | Enterprise Value |
|-----------|---------------|----------|------------------|
| **IFRS-16** | €950m EBITDA | 9.0x | €8.55bn |
| **EBITDAR** | €1,080m EBITDAR | 7.9x | €8.55bn (same) |

---

## VP Assessment Framework

### When to Use Each Approach

**IFRS-16 (Recommended for Accor)**:
✅ Conservative lease-heavy hospitality analysis  
✅ Rating agency and lender preferred  
✅ Captures lease risk in leverage metrics  
✅ IFRS accounting standard compliance  

**EBITDAR (Alternative View)**:
✅ Traditional operating lease treatment  
✅ Higher coverage ratios  
✅ Easier comparability to pre-IFRS-16 deals  
✅ Focus on core operating performance  

---

## Risk Implications

### Covenant Headroom Comparison
```python
# IFRS-16 Headroom (Conservative)
icr_headroom = 2.5 - 2.2  # 0.3x buffer
leverage_headroom = 9.0 - 8.4  # 0.6x buffer

# EBITDAR Headroom (Optimistic)  
icr_headroom = 2.3 - 2.2  # 0.1x buffer (tighter!)
leverage_headroom = 9.0 - 6.3  # 2.7x buffer (much looser)
```

**VP Insight**: IFRS-16 provides more realistic risk assessment for lease-heavy businesses

---

## Conclusion

**Primary Analysis**: IFRS-16 lease-in-debt (conservative, rating agency aligned)  
**Alternative View**: EBITDAR variant shows traditional metrics  
**VP Recommendation**: Lead with IFRS-16, reference EBITDAR for context  

**File Reference**: See `src/modules/ebitdar_variant.py` for implementation

---

**Status**: 🎯 **Extra Credit Complete** - Both lease treatments analyzed
