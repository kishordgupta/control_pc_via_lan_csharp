using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Drawing;
using System.Linq;
using System.Text;
using System.Windows.Forms;
using System.Net;
using System.Net.Sockets;
using System.IO;
using System.Threading;
using MSTSCLib;

namespace Server_PC
{
    public partial class Form1 : Form
    {
        private IPAddress hostIP = null;
        private int hostPort = -1;
        TcpClient tcpClient = null;
        private Thread checkForConnection = null;
        private Thread[] recieve = new Thread[5];
        private string recvDt = null;
        public delegate void rcvData();
        static public int MAX_CONN = 5;
        private string[] ipList;
        NetworkStream[] nStream = null;
        static int thrd = -1;
        private String currentMsg = null;
        private Boolean stopRecieving = false;
        private Boolean sameIP = false;
        private string file = "";
        private string ipselected = "";
        TcpListener myList = null;
        


        public Form1()
        {
            InitializeComponent();
            cmd_send.Enabled = false;
            textBox2.Enabled = false;
            button6.Enabled = false;
            hostIP = getHostIP();
            for (int i = 0; i < recieve.Length ; i++)
            {
                recieve[i] = new Thread(new ThreadStart(recieveData));
            }

        }

        public void addToOutput()
        {
            if (recvDt != null && recvDt!="")
            {
                
                output.Text += "\n Received Data : " + recvDt;
                recvDt = null;
            }

         }

        public void addNotification()
        {
           if (currentMsg != null)
            {
                output.Text += currentMsg + Environment.NewLine;
            }
        }




        private IPAddress getHostIP()
        {
            return Dns.GetHostByName(Dns.GetHostName()).AddressList[0];
        }

        private void cmd_connect_Click(object sender, EventArgs e)
        {

            hostPort = int.Parse(textBox1.Text);
            ipList = new string[MAX_CONN];
            nStream = new NetworkStream[MAX_CONN];
            myList = new TcpListener(hostIP, hostPort);
            myList.Start();
            output.Text += "Listening server started @ " + hostIP.ToString() + Environment.NewLine;
            output.Text += "Listening on " + hostPort + " port" + Environment.NewLine;
            cmd_connect.Enabled = false;
            textBox1.Enabled = false;
            pictureBox1.Visible = false;
            
           
            checkForConnection = new Thread(new ThreadStart(performConnect));
            checkForConnection.Start();
            output.Text += "Waiting for connection . . ." + Environment.NewLine;

        }

        private void performConnect()
        {

            while (true)
            {
                if (myList.Pending())
                {
                    thrd = thrd + 1;
                    tcpClient = myList.AcceptTcpClient();

                    IPEndPoint ipEndPoint = (IPEndPoint)tcpClient.Client.RemoteEndPoint;
                    string clientIP = ipEndPoint.Address.ToString();
                    nStream[thrd] = tcpClient.GetStream();
                    currentMsg = "\n New IP client found :" + clientIP;
                    recieve[thrd].Start();
                 
                    this.Invoke(new rcvData(addNotification));
                    try
                    {
                        addToIPList(clientIP);
                        
                    }
                    catch (InvalidOperationException exp)
                    {
                        Console.Error.WriteLine(exp.Message);
                    }
                    Thread.Sleep(1000);
                }
               
                }


            
        }
       
        
        public bool addToIPList(string IP)
        {
            int i = 0;
            for (i = 0; i < MAX_CONN; i++)
            {
                if (IP.CompareTo(ipList[i]) == 0)
                {
                    sameIP = true;
                    break;

                }


            }
            if (sameIP == false)
            {
                ipList[thrd] = IP;
                Console.WriteLine(ipList[thrd]);
                currentMsg = IP;
                this.Invoke(new rcvData(addToCombo));
                return true;

            }
            else
                return false;

            throw new InvalidOperationException("connecting pc is already in the thread list\nconnection refused");
        }
        
        public void addToCombo()
        {

            comboBox1.Items.Add(currentMsg);
        }


        private void cmd_send_Click(object sender, EventArgs e)
        {


            try
            {
                String str = textBox2.Text.ToString();
                sendData(str);
                output.Text += "\n Sent to " + comboBox1.SelectedItem.ToString() + " : " + str;
                textBox2.Clear();

            }
            catch (Exception ex)
            {
                output.Text += "Error.....\n " + ex.StackTrace;

            }
        }

        private void recieveData()
        {
            NetworkStream nStream = tcpClient.GetStream();
            ASCIIEncoding ascii = null;
            while (!stopRecieving)
            {
                if (nStream.CanRead)
                {
                    byte[] buffer = new byte[64];
                    nStream.Read(buffer, 0, buffer.Length);
                    ascii = new ASCIIEncoding();
                    recvDt = ascii.GetString(buffer);
                    /*Received message checks if it has +@@+ then the ip is disconnected*/
                    bool f =false;
                    f = recvDt.Contains("+@@+");
                    if (f)
                    {
                        string d = "+@@+";
                        recvDt = recvDt.TrimStart(d.ToCharArray());
                        clientDis();
                        stopRecieving = true;

                    }
                   
                    else if (recvDt.Contains("^^"))
                    {
                        new Transmit_File().transfer_file(file, ipselected);
                    }
                    /* ++-- shutsdown/restrt/logoff/abort*/
                    else if (recvDt.Contains("++--"))
                    {
                        string d = "++--";
                        recvDt = recvDt.TrimStart(d.ToCharArray());
                        this.Invoke(new rcvData(addToOutput));
                        clientDis();
                    }
                        /*--++ Normal msg*/
                    else if(recvDt.Contains("--++"))
                    {
                        string d = "--++";
                        recvDt = recvDt.TrimStart(d.ToCharArray());
                        this.Invoke(new rcvData(addToOutput));

                    }
                }
                Thread.Sleep(1000);
            }
  
        }

        public void clientDis()
        {

           if (recvDt != null)
            {
               System.Console.WriteLine("\n Client Disconnected : " + recvDt);
               this.Invoke(new rcvData(clientDisconnected));
               this.Invoke(new rcvData(comboBox1.Items.Clear));
       
             for (int a = 0; a<ipList.Length; a++)
               {
                   Console.WriteLine(ipList[a]);

                 string tr="\0";
                 string aa=recvDt.TrimEnd(tr.ToCharArray());

                 
                   if (ipList[a].Equals(aa))
                   {

                       for(int b=a;ipList[b]!=null;b++)
                       {
                         ipList[b] = ipList[b + 1];
                       }
                       break;
                   }
             
               }

               this.Invoke(new rcvData(addCom));
  
           }
       }
        
        
        public void addCom()
        {
            if (ipList[0] != null)
            {
                for (int c = 0; ipList[c] != null; c++)
                {
                    Console.WriteLine(ipList[c]);
                    comboBox1.Items.Add(ipList[c]);

                }
            }
        
        }
        public void clientDisconnected()
        {
          
            output.Text += "\n Client Disconnected : " + recvDt;
        }





        private void sendData(String data)
        {
            IPAddress ipep =IPAddress.Parse(comboBox1.SelectedItem.ToString());
            Socket server = new Socket(AddressFamily.InterNetwork , SocketType.Stream, ProtocolType.Tcp);
            IPEndPoint ipept = new IPEndPoint( ipep, hostPort);
            NetworkStream nStream = tcpClient.GetStream();
            ASCIIEncoding asciidata = new ASCIIEncoding();
            byte[] buffer = asciidata.GetBytes(data);
            if (nStream.CanWrite)
            {
                nStream.Write(buffer, 0, buffer.Length);
                nStream.Flush();
            }
        }

        private void comboBox1_SelectedIndexChanged(object sender, EventArgs e)
        {
            textBox2.Enabled = true;
            cmd_send.Enabled = true;
            groupBox1.Enabled = true;
            button6.Enabled = true;
            ipselected = comboBox1.SelectedItem.ToString();
        }


            /*Remote desktop*/

        private void button1_Click(object sender, EventArgs e)
        {
           try
            {
                rdp.Server = txtServer.Text;
                rdp.UserName = txtUserName.Text;

                IMsTscNonScriptable secured = (IMsTscNonScriptable)rdp.GetOcx();
                secured.ClearTextPassword = txtPassword.Text;
                rdp.Connect();
            }
            catch (Exception Ex)
            {
            MessageBox.Show("Error Connecting", "Error connecting to remote desktop " + txtServer.Text + " Error:  " + Ex.Message, MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        private void button2_Click(object sender, EventArgs e)
        {
            try
            {
                // Check if connected before disconnecting
                if (rdp.Connected.ToString() == "1")
                    rdp.Disconnect();
            }
            catch (Exception Ex)
            {
                MessageBox.Show("Error Disconnecting", "Error disconnecting from remote desktop " + txtServer.Text + " Error:  " + Ex.Message, MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

                      /*File transfer*/

        private void button6_Click(object sender, EventArgs e)
        {
            FileDialog fDg = new OpenFileDialog();
            if (fDg.ShowDialog() == DialogResult.OK)
            {
                file = fDg.FileName;

                string[] f = file.Split('\\');

                string fnm = f[f.Length - 1];
                fnm = "##" + fnm + "|";
                NetworkStream ns = tcpClient.GetStream();
                if (ns.CanWrite)
                {
                    byte[] bf = new ASCIIEncoding().GetBytes(fnm);
                    ns.Write(bf, 0, bf.Length);
                    ns.Flush();
                }
            }
          


        }

        private void exit_Click(object sender, EventArgs e)
        {
            int i = 0;
            for (i = 0; i < MAX_CONN; i++)
            {
                if (recieve != null)
                    if (recieve[i] != null)
                        recieve[i].Abort();
            }
            if (checkForConnection != null)
                checkForConnection.Abort();
            if (myList != null)
                myList.Stop();
            Application.Exit();

        }

        private void cmd_comand_Click(object sender, EventArgs e)
        {
            try
            {
                if (radioButton1.Checked)
                {
                    currentMsg = "*+*-shutdown";
                    sendData(currentMsg);
                    currentMsg = "\nShutdown initiating to " + comboBox1.SelectedItem.ToString() + " Ip";
                    this.Invoke(new rcvData(addNotification));
                    recvDt = comboBox1.SelectedItem.ToString();
                    clientDis();

                }
                else if (radioButton2.Checked)
                {
                    currentMsg = "*+*-restart";
                    sendData(currentMsg);
                    currentMsg = "\nRestart initiating to " + comboBox1.SelectedItem.ToString() + " Ip";
                    this.Invoke(new rcvData(addNotification));
                    recvDt = comboBox1.SelectedItem.ToString();
                    clientDis();

                }
                else if (radioButton3.Checked)
                {
                    currentMsg = "*+*-logoff";
                    sendData(currentMsg);
                    currentMsg = "\nLogoff to " + comboBox1.SelectedItem.ToString() + " Ip";
                    this.Invoke(new rcvData(addNotification));
                    recvDt = comboBox1.SelectedItem.ToString();
                    clientDis();
                }
                else if (radioButton4.Checked)
                {
                    currentMsg = "*+*-abort";
                    sendData(currentMsg);
                    currentMsg = "\nShutdown / Restart aborted to " + comboBox1.SelectedItem.ToString() + " Ip";
                    this.Invoke(new rcvData(addNotification));
                    recvDt = comboBox1.SelectedItem.ToString();
                    clientDis();
                }
            }

            catch (NullReferenceException exp)
            {
                Console.WriteLine(exp.Message);
            }

            Thread.Sleep(2000);
        }



        
    }

    #region transmit

    class Transmit_File
    {
        StreamWriter writeImageData;
        NetworkStream nStream;

        string Base64ImageData;
        string BlockData;
        int RemainingStringLength = 0;

        bool Done = false;
        public void transfer_file(string filename, string ip_addr)
        {
            Thread.Sleep(1000);
            try
            {
                Console.WriteLine("transfering file to :" + ip_addr);
                TcpClient tcpClient = new TcpClient(ip_addr, 7890);
                nStream = tcpClient.GetStream();
                writeImageData = new StreamWriter(nStream);


                //Change the filename here. If you change the file type, 
                //you must change it on the Server Project too.

                FileStream fs = File.OpenRead(filename);
                byte[] ImageData = new byte[fs.Length];
                fs.Read(ImageData, 0, ImageData.Length);

                Base64ImageData = Convert.ToBase64String(ImageData);

                int startIndex = 0;

                Console.WriteLine("Transfering Data...");

                while (Done == false)
                {
                    while (startIndex < Base64ImageData.Length)
                    {
                        try
                        {
                            BlockData = Base64ImageData.Substring(startIndex, 100);
                            writeImageData.WriteLine(BlockData);
                            writeImageData.Flush();
                            startIndex += 100;
                        }
                        catch (Exception)
                        {
                            RemainingStringLength = Base64ImageData.Length - startIndex;
                            BlockData = Base64ImageData.Substring(startIndex, RemainingStringLength);
                            writeImageData.WriteLine(BlockData);
                            writeImageData.Flush();
                            Done = true;
                            break;
                        }
                    }
                }

                writeImageData.Close();
                tcpClient.Close();
                fs.Close();
                fs.Dispose();
                nStream.Close();
                nStream.Dispose();
                nStream = null;
                tcpClient.Close();
                ImageData = null;
                Base64ImageData = null;

                Console.WriteLine("Transfer Complete");
                MessageBox.Show("File Transfer to " + ip_addr +" is Completed");
            }
            catch (Exception er)
            {
                Console.WriteLine("Unable to connect to server");
                MessageBox.Show("Unable to connect to server");
                Console.WriteLine(er.Message);
            }
        }
    }

    #endregion

  

}
