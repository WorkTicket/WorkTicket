import { View, Text, TouchableOpacity } from "react-native";
import { useSignIn } from "@clerk/clerk-expo";

export default function LoginScreen() {
  const { signIn, isLoaded } = useSignIn();

  if (!isLoaded) return null;

  return (
    <View className="flex-1 justify-center items-center p-6">
      <Text className="text-3xl font-bold mb-2">WorkTicket</Text>
      <Text className="text-gray-500 mb-8">AI for Skilled Trades</Text>
      <TouchableOpacity
        className="bg-blue-600 px-8 py-3 rounded-lg"
        accessibilityLabel="Sign in"
        accessibilityRole="button"
        onPress={() =>
          signIn.authenticateWithRedirect({
            strategy: "oauth_google",
            redirectUrl: "/",
            redirectUrlComplete: "/",
          })
        }
      >
        <Text className="text-white font-semibold">Sign in with Google</Text>
      </TouchableOpacity>
    </View>
  );
}
