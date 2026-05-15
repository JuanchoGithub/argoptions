# Estrategias Avanzadas: Tiempo, Sintéticos y Ratios

Este documento complementa las estrategias de renta, enfocándose en la asimetría temporal, la eficiencia de capital y el uso de ratios, siguiendo la línea de enseñanza de la Escuelita de Opciones.

## 1. Estrategias basadas en el Tiempo (Asimetría Temporal)

Estas estrategias no buscan solo el movimiento del precio, sino la diferencia en la velocidad a la que expiran los contratos.

### A. Calendar Spreads (El Juego del Tiempo)
Se venden opciones de corto plazo y se compran de largo plazo en el mismo strike.
*   **Lógica:** La opción de corto plazo pierde valor (Theta) mucho más rápido que la de largo plazo.
*   **Uso:** Mercado lateral a muy corto plazo, pero con visión alcista/bajista a largo plazo.

### B. Diagonal Spreads (El Híbrido)
Es un Calendar pero con strikes diferentes.
*   **Lógica:** Combina la ganancia por tiempo (Theta) con un sesgo direccional (Delta).
*   **"Poor Man's Covered Call":** Comprar una Call larga (Deep ITM, Delta $\approx 0.80$) y vender Calls cortas (OTM, Delta $\approx 0.20$). Es como tener la acción pero usando una fracción del capital.

---

## 2. Posiciones Sintéticas y Ratios

### A. Posiciones Sintéticas (Eficiencia de Capital)
Permiten imitar la tenencia de un activo sin comprar el activo real.
*   **Sintético Long:** Comprar Call + Vender Put (mismo strike y vencimiento). Se comporta exactamente como tener la acción.
*   **Sintético Short:** Vender Call + Comprar Put.

### B. Ratio Spreads (Renta Agresiva)
Vender más opciones de las que se compran (ej. Ratio 1:2).
*   **Estructura:** Comprar 1 Call y Vender 2 Calls en strikes superiores.
*   **Riesgo:** Tiene riesgo ilimitado si el precio sube demasiado. Por eso la Escuelita recomienda transformarlos en Mariposas comprando una tercera opción lejana como seguro.

---

## 3. Implementación y Operativa en `argoptions`

Al ser estrategias multivariables (tiempo y strike), el proceso de armado es más complejo.

### Operativa para Calendars y Diagonals
1.  **Detección de Vencimientos:**
    *   Ejecuta `chain` para identificar dos fechas de vencimiento: una "Corta" (ej. 15 días) y una "Larga" (ej. 60 días).
2.  **Sincronización de Strikes:**
    *   Usa el **Screen** para encontrar el strike objetivo (ej. Delta 0.50).
    *   Busca ese mismo strike en ambas fechas de vencimiento en la tabla de resultados.
3.  **Cálculo de Spread Temporal:**
    *   Resta el `Mid` de la opción corta del `Mid` de la opción larga. El resultado es el costo de armar el Calendar.

### Operativa para Ratios y Sintéticos
1.  **Cálculo de Costo Neto:**
    *   En la tabla de `argoptions`, identifica los `Mid` de los contratos.
    *   Aplica la fórmula de cantidad: $(\text{Mid}_{compra} \times 1) - (\text{Mid}_{venta} \times 2)$.
2.  **Verificación de Margen:**
    *   Dado que los Ratios implican venta desnuda, monitorea el `Ask` de las opciones vendidas mediante el modo **Auto-chain (`w`)**. Si el `Ask` sube bruscamente, el riesgo de la posición aumenta.

---

## 4. Matriz de Monitoreo Avanzado

| Estrategia | Variable Crítica en `argoptions` | Señal de Alerta (Red Flag) |
| :--- | :--- | :--- |
| **Calendar** | Diferencia de Theta entre vencimientos | Que el precio se mueva agresivamente lejos del strike central. |
| **Diagonal** | Delta de la opción larga | Que la opción larga pierda Delta rápidamente (caída del activo). |
| **Sintético** | Spread Bid-Ask de ambas patas | Un spread ancho en la pata vendida encarece la salida. |
| **Ratio** | Delta de las opciones vendidas | Que el Delta de las vendidas pase a $> 0.60$ (están entrando en el dinero). |

## 5. Referencias
*   **Sugerencia de estudio:** Buscar en los videos de Francisco Mancuso los términos *"Sintéticos"*, *"Diagonales"* y *"Ratios"*.
*   **Enfoque:** Priorizar siempre la transformación de un Ratio en una Mariposa para eliminar el riesgo ilimitado.
