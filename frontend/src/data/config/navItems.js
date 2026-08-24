import HomeIcon from "@/components/icons/HomeIcon.vue"
import LeaveIcon from "@/components/icons/LeaveIcon.vue"
import ExpenseIcon from "@/components/icons/ExpenseIcon.vue"
import SalaryIcon from "@/components/icons/SalaryIcon.vue"
import AttendanceIcon from "@/components/icons/AttendanceIcon.vue"

// Single source of truth for the app's primary navigation — used by the
// mobile bottom tab bar (BottomTabs.vue) and the large-screen sidebar
// (SidebarNav.vue) so both stay in sync with the same items and routes.
export function getNavItems(__) {
	return [
		{
			icon: HomeIcon,
			title: __("Home"),
			route: "/home",
		},
		{
			icon: AttendanceIcon,
			title: __("Attendance"),
			route: "/dashboard/attendance",
		},
		{
			icon: LeaveIcon,
			title: __("Leaves"),
			route: "/dashboard/leaves",
		},
		{
			icon: ExpenseIcon,
			title: __("Expenses"),
			route: "/dashboard/expense-claims",
		},
		{
			icon: SalaryIcon,
			title: __("Salary"),
			route: "/dashboard/salary-slips",
		},
	]
}
