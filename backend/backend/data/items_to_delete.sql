-- SQL to delete old duplicate items

DELETE FROM items WHERE id IN (
  -- Add IDs of items to delete here after review
  -- Example: 1, 2, 3, 4, 5
);
