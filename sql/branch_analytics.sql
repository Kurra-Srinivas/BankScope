-- =============================================================================
-- BankScope — Branch Analytics SQL
-- Canonical Database: bankscope_db
-- Note: Branches is an independent entity in the source dataset without foreign keys
-- in accounts or loans. These queries evaluate the physical network and manager topology.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Query 17: Branch Manager Portfolio Breadth & Multi-Branch Oversight
-- Business Question: What is the distribution of physical branch oversight among bank managers,
-- and which managers are responsible for multi-branch portfolios?
-- SQL Techniques: GROUP BY, COUNT, DENSE_RANK() window function, HAVING.
-- -----------------------------------------------------------------------------
SELECT 
    manager_name,
    COUNT(branch_id) AS branches_managed,
    STRING_AGG(branch_name, ' | ' ORDER BY branch_name) AS branch_names_list,
    DENSE_RANK() OVER (ORDER BY COUNT(branch_id) DESC) AS manager_workload_rank
FROM branches
GROUP BY manager_name
ORDER BY branches_managed DESC, manager_name ASC;


-- -----------------------------------------------------------------------------
-- Query 18: Branch Geographic Gap Analysis (High-Density Customer Cities vs Branch Infrastructure)
-- Business Question: Which top customer population centers have zero direct local branch infrastructure
-- (where branch city is known or unassigned), highlighting prime expansion opportunities for digital-only vs brick-and-mortar strategies?
-- SQL Techniques: CTEs, FULL OUTER JOIN, COALESCE, CASE, Ranking.
-- -----------------------------------------------------------------------------
WITH customer_city_density AS (
    SELECT 
        city,
        COUNT(customer_id) AS customer_count,
        COUNT(DISTINCT c.customer_id) AS unique_customers
    FROM customers c
    GROUP BY city
),
branch_city_presence AS (
    SELECT 
        city,
        COUNT(branch_id) AS local_branch_count
    FROM branches
    WHERE city IS NOT NULL
    GROUP BY city
)
SELECT 
    c.city,
    c.customer_count,
    COALESCE(b.local_branch_count, 0) AS local_branch_count,
    CASE 
        WHEN COALESCE(b.local_branch_count, 0) = 0 THEN 'Digital / Remote Only (No Branch)'
        ELSE 'Served by Local Branch'
    END AS service_model,
    DENSE_RANK() OVER (ORDER BY c.customer_count DESC) AS customer_density_rank
FROM customer_city_density c
LEFT JOIN branch_city_presence b ON c.city = b.city
ORDER BY c.customer_count DESC
LIMIT 20;


-- -----------------------------------------------------------------------------
-- Query 19: Branch Network Nomenclature & Regional Cluster Distribution
-- Business Question: How are physical branches categorized across directional identifiers
-- (e.g. North, South, East, West, Lake, Port), and what is the distribution across regional designations?
-- SQL Techniques: CASE pattern matching with LIKE, COUNT(*), Percentage share window function.
-- -----------------------------------------------------------------------------
WITH branch_regions AS (
    SELECT 
        branch_id,
        branch_name,
        manager_name,
        CASE 
            WHEN branch_name LIKE 'North%' THEN 'Northern Cluster'
            WHEN branch_name LIKE 'South%' THEN 'Southern Cluster'
            WHEN branch_name LIKE 'East%' THEN 'Eastern Cluster'
            WHEN branch_name LIKE 'West%' THEN 'Western Cluster'
            WHEN branch_name LIKE 'Lake%' THEN 'Lakeside District'
            WHEN branch_name LIKE 'Port%' THEN 'Port / Coastal District'
            WHEN branch_name LIKE 'New%' THEN 'New Metro Cluster'
            ELSE 'Central / Metropolitan'
        END AS regional_cluster
    FROM branches
)
SELECT 
    regional_cluster,
    COUNT(branch_id) AS total_branches,
    ROUND(COUNT(branch_id) * 100.0 / SUM(COUNT(branch_id)) OVER (), 2) AS branch_share_pct,
    COUNT(DISTINCT manager_name) AS distinct_managers
FROM branch_regions
GROUP BY regional_cluster
ORDER BY total_branches DESC;
