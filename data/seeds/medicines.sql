-- POLISH-2-MEDICINE-SEED: Optional SQLite seed for the existing medicines table.
-- Run only after at least one active pharmacy exists; this does not create or alter schemas.
INSERT INTO medicines (name, generic_name, category, price, unit, requires_prescription, is_available, pharmacy_id)
SELECT 'Ashwagandha', 'Ashwagandha', 'general wellness', 299, 'bottle', 0, 1, id FROM pharmacies WHERE is_active = 1 LIMIT 1;
INSERT INTO medicines (name, generic_name, category, price, unit, requires_prescription, is_available, pharmacy_id)
SELECT 'Triphala', 'Triphala', 'digestion', 199, 'bottle', 1, 1, id FROM pharmacies WHERE is_active = 1 LIMIT 1;
INSERT INTO medicines (name, generic_name, category, price, unit, requires_prescription, is_available, pharmacy_id)
SELECT 'Amla Juice', 'Amla', 'immunity', 399, 'bottle', 0, 1, id FROM pharmacies WHERE is_active = 1 LIMIT 1;
INSERT INTO medicines (name, generic_name, category, price, unit, requires_prescription, is_available, pharmacy_id)
SELECT 'Giloy Tablet', 'Giloy', 'immunity', 249, 'strip', 0, 1, id FROM pharmacies WHERE is_active = 1 LIMIT 1;
INSERT INTO medicines (name, generic_name, category, price, unit, requires_prescription, is_available, pharmacy_id)
SELECT 'Tulsi Drops', 'Tulsi', 'cold and cough', 189, 'bottle', 0, 1, id FROM pharmacies WHERE is_active = 1 LIMIT 1;
INSERT INTO medicines (name, generic_name, category, price, unit, requires_prescription, is_available, pharmacy_id)
SELECT 'Neem Capsules', 'Neem', 'skin wellness', 229, 'bottle', 0, 1, id FROM pharmacies WHERE is_active = 1 LIMIT 1;
INSERT INTO medicines (name, generic_name, category, price, unit, requires_prescription, is_available, pharmacy_id)
SELECT 'Brahmi Vati', 'Brahmi', 'stress support', 219, 'bottle', 1, 1, id FROM pharmacies WHERE is_active = 1 LIMIT 1;
INSERT INTO medicines (name, generic_name, category, price, unit, requires_prescription, is_available, pharmacy_id)
SELECT 'Shatavari Kalpa', 'Shatavari', 'women wellness', 349, 'pack', 0, 1, id FROM pharmacies WHERE is_active = 1 LIMIT 1;
INSERT INTO medicines (name, generic_name, category, price, unit, requires_prescription, is_available, pharmacy_id)
SELECT 'Sitopaladi Churna', 'Sitopaladi', 'cold and cough', 159, 'pack', 0, 1, id FROM pharmacies WHERE is_active = 1 LIMIT 1;
INSERT INTO medicines (name, generic_name, category, price, unit, requires_prescription, is_available, pharmacy_id)
SELECT 'Avipattikar Churna', 'Avipattikar', 'acidity', 179, 'pack', 0, 1, id FROM pharmacies WHERE is_active = 1 LIMIT 1;
