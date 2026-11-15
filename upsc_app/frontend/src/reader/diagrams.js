export const diagrams = {
  'National Education Day': [
    ['Education mind map', `mindmap
  root((National Education Day))
    Maulana Abul Kalam Azad
      First Union Education Minister
      Universal primary education
      Scientific learning
    Education
      Digital learning and EdTech
      Inclusive and equitable access
      Skills and modern curricula
      NEP 2020 alignment`],
  ],
  Anaemia: [
    ['Classification in the source note', `flowchart TD
  A[Anaemia] --> B[Iron deficiency]
  A --> C[Vitamin B12 or folate deficiency]
  A --> D[Aplastic anaemia]
  A --> E[Haemolytic anaemia]
  A --> F[Inherited disorders: sickle cell disease or thalassaemia]
  A --> G[Chronic disease]
  A --> H[Blood loss or parasitic infection]`],
    ['Hepcidin–ferroportin pathway', `flowchart LR
  L[Liver] --> H[Hepcidin]
  H --> F[ binds ferroportin ]
  F --> I[Internalisation and degradation]
  I --> A[Reduced intestinal iron absorption]
  I --> R[Reduced iron release from macrophages and stores]`],
    ['Diagnostic pathway', `flowchart TD
  A[Suspected anaemia] --> B[Complete blood count]
  B --> C[Haemoglobin, RBC count, haematocrit]
  C --> D[MCV and peripheral smear]
  D --> E[Serum ferritin and reticulocyte count]
  E --> F[Investigate B12 and folate if indicated]
  F --> G[Electrophoresis or HPLC for haemoglobin variants]`],
  ],
  'Exercise VAJRA-SAT': [
    ['Outbreak preparedness sequence', `flowchart LR
  A[Early detection] --> B[Surveillance]
  B --> C[Laboratory confirmation]
  C --> D[Epidemiological investigation]
  D --> E[Animal movement control]
  E --> F[Emergency vaccination readiness]
  F --> G[Risk communication]`],
  ],
  'Muhurat Trading': [
    ['Institutional timeline', `timeline
  title Muhurat Trading
  1957 : BSE institutionalises the organised session
  1992 : NSE adopts the practice`],
    ['Typical session', `flowchart LR
  A[Exchange-notified schedule] --> B[Pre-opening session]
  B --> C[Short continuous trading window]
  C --> D[Closing session]
  E[Chopda Pujan tradition] -. historical context .-> A`],
  ],
  'Exercise Naseem Al Bahr': [
    ['Exercise comparison', `flowchart LR
  A[Naseem Al Bahr] --> A1[Bilateral naval exercise]
  A --> A2[India and Oman]
  A --> A3[Maritime cooperation]
  B[RAHAT MITRA] --> B1[Tri-services HADR exercise]
  B --> B2[India and Myanmar]
  B --> B3[Disaster response and interoperability]`],
  ],
  'Gulf of California': [
    ['Regional geography', `flowchart LR
  A[Baja California Peninsula] --- G[Gulf of California]
  M[Mainland Mexico] --- G
  G --- P[Pacific Ocean]
  G --> V[Vaquita habitat; exact boundaries not shown]`],
  ],
  'Kīlauea Volcano': [
    ['Hotspot context', `flowchart LR
  P[Pacific Plate moves] --> H[Relatively stationary mantle hotspot]
  H --> V[Kīlauea: shield volcano on Hawaiʻi Island]
  P --> C[Hawaiian–Emperor volcanic chain]`],
  ],
}

export function diagramsFor(title) {
  const direct = diagrams[title]
  if (direct) return direct
  if (/VAJRA-SAT/i.test(title)) return diagrams['Exercise VAJRA-SAT']
  if (/Gulf of California/i.test(title)) return diagrams['Gulf of California']
  if (/Kīlauea|Kilauea|Hawai/i.test(title)) return diagrams['Kīlauea Volcano']
  if (/Naseem Al Bahr/i.test(title)) return diagrams['Exercise Naseem Al Bahr']
  return []
}
