import { Tabs } from "expo-router";

const COLORS = {
  headerBackground: "#1e40af",
  headerTint: "#fff",
} as const;

export default function TabLayout() {
  return (
    <Tabs
      screenOptions={{
        headerStyle: { backgroundColor: COLORS.headerBackground },
        headerTintColor: COLORS.headerTint,
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: "Today's Jobs",
          headerTitle: "WorkTicket",
        }}
      />
      <Tabs.Screen
        name="start-job"
        options={{
          title: "Start Job",
          headerTitle: "New Job",
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: "Profile",
        }}
      />
    </Tabs>
  );
}
