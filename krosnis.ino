// vim: ft=cpp
#include <SPI.h>
#include "Adafruit_MAX31855.h"

#define PIN_BUTTON_GND 4
#define PIN_BUTTON 5
#define PIN_TRIAC_GND 6
#define PIN_TRIAC 7

#define PIN_CS   10
#define PIN_CLK  12
#define PIN_DO   13
Adafruit_MAX31855 thermocouple(PIN_CS);

#define TIMER1_FREQ 100
#define TIMER1_PRELOAD (65536 - 16000000 / 256 / TIMER1_FREQ)

volatile uint8_t triac_power = 0;
uint8_t pwm_counter = 0;

// Timer1 overflow interrupt
ISR(TIMER1_OVF_vect) {
  TCNT1 = TIMER1_PRELOAD; // Reschedule.
  pwm_counter = (pwm_counter + 1) % 255;
  digitalWrite(PIN_TRIAC, pwm_counter < triac_power);
}

void setup() {
    pinMode(PIN_TRIAC_GND, OUTPUT);
    digitalWrite(PIN_TRIAC_GND, LOW);
    pinMode(PIN_TRIAC, OUTPUT);
    digitalWrite(PIN_TRIAC, LOW);

    pinMode(PIN_BUTTON_GND, OUTPUT);
    digitalWrite(PIN_BUTTON_GND, LOW);
    pinMode(PIN_BUTTON, INPUT_PULLUP);

    // wait for MAX chip to stabilize
    delay(500);

    noInterrupts();
    // Setup Timer1.
    TCCR1A = 0;
    TCCR1B = 0;
    TCNT1 = TIMER1_PRELOAD;
    TCCR1B |= (1 << CS12);    // 256 prescaler 
    TIMSK1 |= (1 << TOIE1);   // enable timer overflow interrupt
    interrupts();

    Serial.begin(115200);
}

void loop() {
    if (Serial) {
        if (Serial.available()) {
            switch (Serial.read()) {
                case 'P':
                    triac_power = Serial.read();
                    break;
            }
        }

        unsigned long t_ms = millis();
        Serial.print(t_ms);
        Serial.print(",");

        Serial.print(triac_power);
        Serial.print(",");

        float temp_outside = thermocouple.readInternal();
        Serial.print(temp_outside);
        Serial.print(",");

        float temp_inside = thermocouple.readCelsius();
        Serial.print(temp_inside);
        Serial.println();
    }

    delay(100);
}
