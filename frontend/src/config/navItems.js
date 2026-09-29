import HomeIcon from "@/components/icons/HomeIcon.vue"
import AttendanceIcon from "@/components/icons/AttendanceIcon.vue"
import LeaveIcon from "@/components/icons/LeaveIcon.vue"
import ExpenseIcon from "@/components/icons/ExpenseIcon.vue"
import SalaryIcon from "@/components/icons/SalaryIcon.vue"

/**
 * Shared primary navigation list, consumed by both the mobile
 * `BottomTabs` tab bar and the desktop `DesktopShell` sidebar, so the two
 * surfaces always point at the same real routes.
 *
 * `__` is the app's translate function (injected via `$translate`); it is
 * passed in rather than imported so this stays a plain data module usable
 * outside a component's `setup()`.
 */
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
