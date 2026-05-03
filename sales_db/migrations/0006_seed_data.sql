-- Seed data: two pipelines + initial admin user (Michael).
-- ON CONFLICT DO NOTHING keeps the SQL safe to execute manually too;
-- the migration runner alone will only execute this once via checksum tracking.

INSERT INTO pipelines (slug, name, stages) VALUES
('end_buyer_sales', 'End-buyer sales',
  '[
    {"id":"new","name":"New","order":1,"default_probability":5},
    {"id":"contacted","name":"Contacted","order":2,"default_probability":10},
    {"id":"engaged","name":"Engaged","order":3,"default_probability":20},
    {"id":"meeting_booked","name":"Meeting booked","order":4,"default_probability":35},
    {"id":"demo_held","name":"Demo held","order":5,"default_probability":50},
    {"id":"proposal_sent","name":"Proposal sent","order":6,"default_probability":65},
    {"id":"negotiation","name":"Negotiation","order":7,"default_probability":80},
    {"id":"won","name":"Won","order":8,"default_probability":100},
    {"id":"lost","name":"Lost","order":9,"default_probability":0},
    {"id":"nurture","name":"Nurture","order":10,"default_probability":5}
  ]'::jsonb),
('eor_partnership', 'EOR partnership',
  '[
    {"id":"identified","name":"Identified","order":1,"default_probability":5},
    {"id":"mapped","name":"Mapped","order":2,"default_probability":10},
    {"id":"initial_call","name":"Initial call","order":3,"default_probability":20},
    {"id":"technical_eval","name":"Technical evaluation","order":4,"default_probability":35},
    {"id":"commercial_discussion","name":"Commercial discussion","order":5,"default_probability":50},
    {"id":"pilot_design","name":"Pilot design","order":6,"default_probability":65},
    {"id":"pilot_active","name":"Pilot active","order":7,"default_probability":80},
    {"id":"partnership_signed","name":"Partnership signed","order":8,"default_probability":100},
    {"id":"lost","name":"Lost","order":9,"default_probability":0},
    {"id":"paused","name":"Paused","order":10,"default_probability":10}
  ]'::jsonb)
ON CONFLICT (slug) DO NOTHING;

INSERT INTO users (email, full_name, role) VALUES
('michael.gill@globalkinect.co.uk', 'Michael Gill', 'admin')
ON CONFLICT (lower(email)) DO NOTHING;
