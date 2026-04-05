# Operator Console - Interaction Polish

## Overview

The operator console has been enhanced with keyboard shortcuts, power-user ergonomics, and a dedicated accounts view to support faster operator workflows and reduce friction in daily operations.

## Keyboard Shortcuts

### Navigation (Single Key Press)

Press any of these keys to navigate instantly:

| Key | Action |
|-----|--------|
| **G** | Go to Dashboard |
| **D** | Go to Lead Discovery |
| **I** | Go to Lead Intake |
| **A** | Go to Accounts & Buyers |
| **Q** | Go to Outreach Queue |
| **R** | Go to Run Monitor |
| **?** | Open Help (this page) |

### Queue Actions (Shift + Letter)

When viewing the Outreach Queue, use these to approve or hold items quickly:

| Shortcut | Action |
|----------|--------|
| **Shift+A** | Approve the first visible draft (make it ready to send) |
| **Shift+H** | Hold the first visible draft (keep out of current send) |
| **Shift+S** | Mark Sent (after manual execution) |
| **Shift+G** | Regenerate draft (if copy needs improvement) |

### Search & Filtering

| Shortcut | Action |
|----------|--------|
| **Ctrl+K** (Windows/Linux) or **Cmd+K** (Mac) | Focus search box and select all text |

### Keyboard Hints

Keyboard shortcuts are displayed as small hints on buttons:

```
[Approve] <Shift+A>
[Hold] <Shift+H>
```

Hover over buttons to see their shortcut in the tooltip, or check the Help page.

## Power User Features

### View Toggle: Cards vs. Tables

Each list page (Discovery, Intake, Queue, Accounts) now includes a **view toggle** in the toolbar:

- **Cards** (default) – Full-detail card view with all information displayed
- **Table** (compact) – Dense table with columns optimized for scanning and bulk actions

Your preference is saved in browser storage and persists across sessions.

#### When to Use Each View

**Use Card View for:**
- Reviewing evidence and detailed context
- Evaluating commercial fit
- Reading full email copy before approval
- First-time operators getting familiar with records

**Use Table View for:**
- High-volume triage and filtering
- Quick status checks
- Identifying patterns and anomalies
- Power users doing 50+ decisions per session

### Filter & Search Improvements

- **Status chips** remain clickable for quick filtering
- **Smart search** – Type multiple words to apply AND logic
  - Example: `saudi payroll` finds companies in Saudi Arabia with Payroll interest
- **Visual feedback** – Active filters are highlighted
- **Reset button** – Clears all filters in one click

### Accounts & Buyers Tab

A new dedicated view aggregates all activity by company:

**What you see:**
- Company name and primary country
- Total activity count across Discovery, Intake, and Queue
- All identified buyers for the account
- Quick links to view the company in each pipeline stage

**Use cases:**
- Understanding account engagement level before outreach
- Spotting duplicate buyer entries across stages
- Planning account-level strategy (e.g., "How many touches do we have here?")
- Identifying which buyers are active in which stages

**Navigation:**
- Press `A` to jump to the Accounts view
- Click any company to see its related links
- Use the search bar to filter by company name or country

## Operator Workflow Improvements

### Typical High-Volume Session

1. Press `Q` to go to Outreach Queue
2. Review filters (e.g., status="Ready to send")
3. Switch to **Table View** for dense scanning
4. Use keyboard shortcuts to approve/hold/mark sent quickly
5. Press `?` anytime to refresh your shortcut memory

### Account-Based Review

1. Press `A` to see Accounts & Buyers
2. Scan for accounts with high activity
3. Click "View Queue" to see pending outreach for that company
4. Approve the strongest buyer-motion combinations
5. Use keyboard shortcuts to move through them fast

### Discovery Qualification

1. Press `D` to go to Lead Discovery
2. Filter by status="Review" to see new signals
3. Evaluate buyer fit and commercial case per the operator guide
4. Use status chips to move records through the workflow

## Help & Reference

Within the operator console:

- Press `?` to access the full keyboard shortcuts guide
- Hover over any button to see its keyboard shortcut in tooltip
- Click the **Help** link in the toolbar

## Browser Compatibility

- All keyboard shortcuts work in modern browsers (Chrome, Firefox, Safari, Edge)
- View preference (Card/Table) stored in localStorage
- No external dependencies or extensions required

## Accessibility Notes

- Keyboard shortcuts do not interfere with form inputs (search, filters)
- All buttons remain clickable for mouse users
- Shortcuts are optional—full functionality via mouse clicks remains
- Keyboard hints are visible but subtle for screen readers

## Future Enhancements

Possible future improvements:

- Customizable keyboard shortcuts
- Bulk actions (select multiple, action all)
- Keyboard navigation between rows (arrow keys)
- Column sorting in table view
- Export/batch operations
- Dark mode toggle (Ctrl+Shift+D?)

## Troubleshooting

**Shortcuts not working?**
- Make sure focus is not in a text input field
- Check that you're not holding Alt (may trigger browser menu)
- Refresh the page
- Check browser console for JS errors

**View toggle disappeared?**
- Clear browser cache
- Ensure JavaScript is enabled
- Try a different browser

**Can't see keyboard hints on buttons?**
- They appear only on the Outreach Queue page
- Check your browser's zoom level (100% for best visibility)
- Visit the Help page for reference table
